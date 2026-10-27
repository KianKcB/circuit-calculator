"""Linear resistive DC analysis; see ARCHITECTURE.md for conventions and limits."""

from dataclasses import dataclass
from fractions import Fraction
import math
from types import MappingProxyType
from typing import Mapping, Tuple

from circuit import Circuit, CurrentSource, Resistor, VoltageSource


class DCError(ValueError):
    """Base class for a circuit that cannot be analyzed by this DC engine."""


class MissingReferenceError(DCError):
    """DC analysis requires an explicit voltage reference."""


class FloatingNetworkError(DCError):
    """Some node voltages have no resistive or voltage constraint to reference."""


class ContradictorySourceError(DCError):
    """Ideal voltage-source constraints contradict each other."""


class NonUniqueSolutionError(DCError):
    """Redundant ideal voltage constraints leave source currents undetermined."""


class InconsistentCurrentError(DCError):
    """Net imposed current into an unanchored region violates KCL."""


class NumericalError(DCError):
    """Numerical range, conditioning, or residual checks prevent a safe result."""


class SingularSystemError(NumericalError):
    """The numerical backend could not solve the assembled system."""


@dataclass(frozen=True)
class DCSystem:
    node_order: Tuple[str, ...]
    source_order: Tuple[str, ...]
    matrix: Tuple[Tuple[float, ...], ...]
    rhs: Tuple[float, ...]
    reference_node: str


@dataclass(frozen=True)
class ElementResult:
    voltage_volts: float
    current_amperes: float
    power_watts: float


@dataclass(frozen=True)
class DCResult:
    reference_node: str
    node_voltages: Mapping[str, float]
    elements: Mapping[str, ElementResult]
    scaled_condition_number: float
    max_kcl_residual_amperes: float
    power_balance_watts: float


def _terminals(element):
    if type(element) is Resistor:
        return element.node_a, element.node_b
    if type(element) is VoltageSource:
        return element.plus_node, element.minus_node
    if type(element) is CurrentSource:
        return element.from_node, element.to_node
    raise TypeError("DC analysis supports only Resistor, VoltageSource and CurrentSource")


def _check_topology(circuit):
    if not isinstance(circuit, Circuit):
        raise TypeError("circuit must be a Circuit")
    if circuit.reference_node is None:
        raise MissingReferenceError("DC analysis requires reference_node")
    paths = {node: [] for node in circuit.nodes}
    constraints = {node: [] for node in circuit.nodes}
    for element in circuit.elements:
        a, b = _terminals(element)
        if not isinstance(element, CurrentSource):
            paths[a].append(b)
            paths[b].append(a)
        if isinstance(element, VoltageSource):
            voltage = Fraction(element.voltage_volts)
            constraints[a].append((b, -voltage))
            constraints[b].append((a, voltage))

    # An ideal-source cycle makes at least one branch current indeterminate.
    # Compare exact values of the supplied floats, not rounded potentials.
    potentials = {}
    redundant = False
    for start in circuit.nodes:
        if start in potentials:
            continue
        potentials[start] = Fraction(0)
        pending = [start]
        vertices = edges = 0
        while pending:
            node = pending.pop()
            vertices += 1
            edges += len(constraints[node])
            for other, difference in constraints[node]:
                expected = potentials[node] + difference
                if other in potentials:
                    if potentials[other] != expected:
                        raise ContradictorySourceError(
                            "contradictory ideal voltage constraints near '{}'".format(other))
                else:
                    potentials[other] = expected
                    pending.append(other)
        redundant |= edges // 2 >= vertices
    if redundant:
        raise NonUniqueSolutionError("ideal voltage-source loop leaves source currents non-unique")

    reached = {circuit.reference_node}
    pending = [circuit.reference_node]
    while pending:
        for other in paths[pending.pop()]:
            if other not in reached:
                reached.add(other)
                pending.append(other)
    missing = [node for node in circuit.nodes if node not in reached]
    if missing:
        unchecked = set(missing)
        while unchecked:
            start = next(node for node in missing if node in unchecked)
            region = {start}
            pending = [start]
            unchecked.remove(start)
            while pending:
                for other in paths[pending.pop()]:
                    if other in unchecked:
                        unchecked.remove(other)
                        region.add(other)
                        pending.append(other)
            net_current = Fraction(0)
            for element in circuit.elements:
                if isinstance(element, CurrentSource):
                    net_current += ((element.to_node in region) - (element.from_node in region)) * Fraction(element.current_amperes)
            if net_current:
                raise InconsistentCurrentError(
                    "current-source cutset violates KCL in region containing '{}'".format(start))
        raise FloatingNetworkError(
            "no resistor/voltage-source path to reference for: {}".format(
                ", ".join(missing)))


def _finite(value, label):
    if not math.isfinite(value):
        raise NumericalError("{} exceeds finite floating-point range".format(label))
    return value


def assemble_dc(circuit: Circuit) -> DCSystem:
    """Validate topology and assemble immutable MNA coefficients in SI units."""
    _check_topology(circuit)
    nodes = tuple(node for node in circuit.nodes if node != circuit.reference_node)
    sources = tuple(e.name for e in circuit.elements if isinstance(e, VoltageSource))
    indices = {node: index for index, node in enumerate(nodes)}
    branches = {name: len(nodes) + index for index, name in enumerate(sources)}
    size = len(nodes) + len(sources)
    matrix = [[0.0] * size for _ in range(size)]
    rhs = [0.0] * size
    for element in circuit.elements:
        a, b = _terminals(element)
        terminals = ((indices.get(a), 1.0), (indices.get(b), -1.0))
        if isinstance(element, Resistor):
            conductance = _finite(1.0 / element.resistance_ohms, element.name + " conductance")
            if conductance == 0:
                raise NumericalError(element.name + " conductance underflow")
            for row, row_sign in terminals:
                if row is not None:
                    for col, col_sign in terminals:
                        if col is not None:
                            matrix[row][col] += row_sign * col_sign * conductance
        elif isinstance(element, CurrentSource):
            for row, sign in terminals:
                if row is not None:
                    rhs[row] -= sign * element.current_amperes
        else:
            branch = branches[element.name]
            for row, sign in terminals:
                if row is not None:
                    matrix[row][branch] += sign
                    matrix[branch][row] += sign
            rhs[branch] = element.voltage_volts
    for row in matrix:
        for value in row:
            _finite(value, "assembled matrix")
    for value in rhs:
        _finite(value, "assembled right-hand side")
    return DCSystem(nodes, sources, tuple(tuple(row) for row in matrix),
                    tuple(rhs), circuit.reference_node)


def _sum(values, label):
    try:
        return _finite(math.fsum(values), label)
    except OverflowError as error:
        raise NumericalError(label + " overflow") from error


def _check_residual(residual, terms, absolute_tolerance, label):
    # Normalize first to avoid overflowing the sum of absolute magnitudes.
    scale = max([absolute_tolerance] + [abs(value) for value in terms])
    bound = absolute_tolerance / scale + 1e-9 * math.fsum(abs(v) / scale for v in terms)
    if abs(residual) / scale > bound:
        raise NumericalError(label + " residual exceeds tolerance")


def solve_dc(circuit: Circuit) -> DCResult:
    """Solve a small linear DC network using optional NumPy dense linear algebra.

    Raises DCError subclasses for topology/numerical failures; TypeError for
    unsupported input. Missing NumPy raises ImportError with installation advice.
    Returned dictionaries are read-only and own their data.
    """
    system = assemble_dc(circuit)
    try:
        import numpy as np
    except ImportError as error:
        raise ImportError("DC solving requires: python -m pip install -r requirements-dc.txt") from error

    size = len(system.rhs)
    condition = 1.0
    solution = []
    if size:
        matrix = np.array(system.matrix, dtype=float)
        rhs = np.array(system.rhs, dtype=float)
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise", under="raise"):
                row_scale = np.max(np.abs(matrix), axis=1)
                scaled = matrix / row_scale[:, None]
                col_scale = np.max(np.abs(scaled), axis=0)
                scaled = scaled / col_scale[None, :]
                scaled_rhs = rhs / row_scale
                condition = float(np.linalg.cond(scaled))
                if not math.isfinite(condition) or condition > 1e12:
                    raise NumericalError("scaled matrix is ill-conditioned (condition={:.3g})".format(condition))
                solution = np.linalg.solve(scaled, scaled_rhs) / col_scale
        except np.linalg.LinAlgError as error:
            raise SingularSystemError("DC matrix is singular or factorization failed") from error
        except FloatingPointError as error:
            raise NumericalError("DC scaling/solve exceeded floating-point range") from error
        for value in solution:
            _finite(float(value), "DC solution")

    voltages = {system.reference_node: 0.0}
    voltages.update((node, float(solution[i])) for i, node in enumerate(system.node_order))
    source_currents = {name: float(solution[len(system.node_order) + i])
                       for i, name in enumerate(system.source_order)}
    results = {}
    currents = {node: [] for node in circuit.nodes}
    for element in circuit.elements:
        a, b = _terminals(element)
        voltage = _finite(voltages[a] - voltages[b], element.name + " voltage")
        if isinstance(element, Resistor):
            current = _finite(voltage / element.resistance_ohms, element.name + " current")
            if voltage != 0 and current == 0:
                raise NumericalError(element.name + " current underflow")
        elif isinstance(element, CurrentSource):
            current = element.current_amperes
        else:
            current = source_currents[element.name]
            _check_residual(voltage - element.voltage_volts,
                            [voltages[a], voltages[b], element.voltage_volts],
                            1e-12, element.name + " voltage constraint")
        power = _finite(voltage * current, element.name + " power")
        if voltage != 0 and current != 0 and power == 0:
            raise NumericalError(element.name + " power underflow")
        results[element.name] = ElementResult(voltage, current, power)
        currents[a].append(current)
        currents[b].append(-current)
    residuals = []
    for node, terms in currents.items():
        residual = _sum(terms, "KCL")
        _check_residual(residual, terms, 1e-12, "KCL at " + node)
        residuals.append(abs(residual))
    powers = [value.power_watts for value in results.values()]
    balance = _sum(powers, "power balance")
    _check_residual(balance, powers, 1e-12, "power balance")
    return DCResult(system.reference_node, MappingProxyType(voltages),
                    MappingProxyType(results), condition, max(residuals), balance)
