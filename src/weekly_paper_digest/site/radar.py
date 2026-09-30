"""Server-rendered SVG radar chart for the five ranking dimensions."""
from __future__ import annotations

import math
from dataclasses import dataclass

from markupsafe import Markup, escape

# Clockwise from the top, per the UI spec.
AXES = ("novelty", "technical", "evidence", "impact", "credibility")
MAX_SCORE = 5
WIDTH, HEIGHT = 320, 270
CX, CY, R = WIDTH / 2, 138, 92


@dataclass(frozen=True)
class Point:
    x: float
    y: float


def vertex(axis_index: int, value: float) -> Point:
    """Position of `value` (0..MAX_SCORE) on axis `axis_index`; axis 0 points straight up."""
    angle = -math.pi / 2 + axis_index * 2 * math.pi / len(AXES)
    r = R * max(0.0, min(value, MAX_SCORE)) / MAX_SCORE
    return Point(round(CX + r * math.cos(angle), 2), round(CY + r * math.sin(angle), 2))


def _poly(points: list[Point]) -> str:
    return " ".join(f"{p.x},{p.y}" for p in points)


def radar_svg(scores: dict[str, int], reasons: dict[str, str]) -> Markup:
    parts = [
        f'<svg class="radar" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" '
        f'aria-label="Radar chart of the five ranking dimensions">'
    ]
    for level in range(1, MAX_SCORE + 1):
        ring = [vertex(i, level) for i in range(len(AXES))]
        parts.append(f'<polygon class="radar-grid" points="{_poly(ring)}"/>')
    for i in range(len(AXES)):
        end = vertex(i, MAX_SCORE)
        parts.append(f'<line class="radar-grid" x1="{CX}" y1="{CY}" x2="{end.x}" y2="{end.y}"/>')

    data = [vertex(i, scores[axis]) for i, axis in enumerate(AXES)]
    parts.append(f'<polygon class="radar-area" points="{_poly(data)}"/>')
    for p in data:
        parts.append(f'<circle class="radar-dot" cx="{p.x}" cy="{p.y}" r="3.5"/>')

    for i, axis in enumerate(AXES):
        angle = -math.pi / 2 + i * 2 * math.pi / len(AXES)
        dx, dy = math.cos(angle), math.sin(angle)
        label = Point(round(CX + (R + 16) * dx, 2), round(CY + (R + 14) * dy + (6 if dy > 0.5 else 0), 2))
        anchor = "middle" if abs(dx) < 0.1 else ("start" if dx > 0 else "end")
        tip = escape(f"{axis.capitalize()} {scores[axis]}/{MAX_SCORE} — {reasons.get(axis, '')}")
        parts.append(
            f'<text class="radar-label" x="{label.x}" y="{label.y}" text-anchor="{anchor}" '
            f'dominant-baseline="middle"><title>{tip}</title>{axis.capitalize()} '
            f'<tspan class="radar-value">{scores[axis]}</tspan></text>'
        )
    parts.append("</svg>")
    return Markup("".join(parts))
