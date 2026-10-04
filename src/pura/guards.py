"""Chain of Responsibility: guardas de segurança aplicados a toda decisão antes do atuador."""
from __future__ import annotations

from dataclasses import dataclass

from .config import RoomSpec, Settings
from .model.dynamics import sleep_caps
from .models import Decision, Reading


@dataclass
class GuardContext:
    settings: Settings
    spec: RoomSpec
    decision: Decision
    reading: Reading | None
    stale: bool
    sleeping: bool
    now: float
    prev: Decision | None = None
    last_change_ts: float = 0.0
    emergency: bool = False
    halt: bool = False


class Guard:
    def __init__(self):
        self._next: Guard | None = None

    def set_next(self, nxt: Guard) -> Guard:
        self._next = nxt
        return nxt

    def handle(self, ctx: GuardContext) -> GuardContext:
        self.apply(ctx)
        if self._next and not ctx.halt:
            self._next.handle(ctx)
        return ctx

    def apply(self, ctx: GuardContext) -> None:
        raise NotImplementedError


class SafeModeGuard(Guard):
    """Sem dado válido => ventilação mínima garantida (nunca 'desligado')."""

    def apply(self, ctx):
        if ctx.stale or ctx.reading is None or ctx.reading.co2 is None:
            ctx.decision = Decision(ctx.spec.name, 1, 0, "safe", "sem dados válidos: ventilação mínima")
            ctx.halt = True


class CeilingGuard(Guard):
    """Teto rígido de CO2: segurança vence ruído e anti short-cycling."""

    def apply(self, ctx):
        if ctx.reading.co2 > ctx.settings.co2_ceiling:
            d = ctx.decision
            d.exhaust, d.mode = max(d.exhaust, 2), "emergency"
            d.reason = f"CO2 {ctx.reading.co2:.0f} ppm acima do teto"
            ctx.emergency = True


class NoiseGuard(Guard):
    def apply(self, ctx):
        if ctx.sleeping and not ctx.emergency:
            u_cap, f_cap = sleep_caps(ctx.settings.noise_sleep_db)
            d = ctx.decision
            d.exhaust, d.purifier = min(d.exhaust, u_cap), min(d.purifier, f_cap)


class MinRuntimeGuard(Guard):
    """Anti short-cycling: não inverte liga/desliga antes de min_run_s."""

    def apply(self, ctx):
        if ctx.emergency or ctx.prev is None or ctx.prev.mode == "safe":
            return
        if ctx.now - ctx.last_change_ts < ctx.settings.min_run_s:
            d, p = ctx.decision, ctx.prev
            if (d.exhaust > 0) != (p.exhaust > 0):
                d.exhaust, d.reason = p.exhaust, (d.reason + " [min-run exaustor]").strip()
            if (d.purifier > 0) != (p.purifier > 0):
                d.purifier, d.reason = p.purifier, (d.reason + " [min-run purificador]").strip()


def build_chain() -> Guard:
    head = SafeModeGuard()
    head.set_next(CeilingGuard()).set_next(NoiseGuard()).set_next(MinRuntimeGuard())
    return head
