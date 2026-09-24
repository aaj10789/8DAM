"""The existing x=8 inter-QPU LER noise convention, with no idle noise."""
from collections import Counter
import stim


def noisy_circuit(circuit, p_link, p_local=1e-4):
    result = stim.Circuit()
    coords = circuit.get_final_qubit_coordinates()
    crossings = Counter()
    total_cx = 0
    for op in circuit:
        targets = op.targets_copy()
        if op.name == 'CX':
            for a, b in zip(targets[::2], targets[1::2]):
                crossing = (coords[a.value][0] < 8) != (coords[b.value][0] < 8)
                total_cx += 1
                if crossing:
                    crossings[tuple(sorted((a.value, b.value)))] += 1
                result.append('CX', [a, b])
                result.append('DEPOLARIZE2', [a, b], p_link if crossing else p_local)
        elif op.name in ['M', 'MX']:
            result.append(op.name, targets, p_local)
        elif op.name in ['R', 'RX', 'H', 'X']:
            result.append(op)
            result.append('DEPOLARIZE1', targets, p_local)
        elif op.name in ['TICK', 'QUBIT_COORDS', 'DETECTOR', 'OBSERVABLE_INCLUDE', 'SHIFT_COORDS']:
            result.append(op)
        else:
            raise ValueError(f'Uncovered instruction: {op.name}')
    boundary = {
        'boundary_x': 8,
        'qpu_a': 'x < 8',
        'qpu_b': 'x >= 8',
        'crossing_rule': '(x1 < 8) != (x2 < 8)',
        'total_cx': total_cx,
        'crossing_cx': sum(crossings.values()),
        'distinct_crossing_links': len(crossings),
        'edges': [
            {'qubits': list(edge), 'occurrences': count,
             'coordinates': [coords[q] for q in edge]}
            for edge, count in sorted(crossings.items())
        ],
        'p_local': p_local,
        'p_link': p_link,
        'idle_noise': False,
    }
    return result, boundary
