"""SilenceMonitor: dead-man по last_seen_at (блок F плана, день 4).

Edge за NAT нельзя опросить: если telemetry/events/health молчат дольше
порога — узел offline и пишется alerts(silence_started). Возврат данных
(ingest уже ставит status='online') закрывает инцидент silence_resolved.
«Никогда не подключался» (last_seen_at IS NULL) от «пропал» отличается:
алерт только у узлов, которые уже были живы.
"""

import asyncio

import loguru

from src.domain.ports.health_repository import HealthRepository


class SilenceMonitor:
    def __init__(
        self,
        health: HealthRepository,
        *,
        stale_after_sec: int,
        poll_interval_sec: int,
    ) -> None:
        self._health = health
        self._stale_after_sec = stale_after_sec
        self._poll_interval_sec = poll_interval_sec

    async def tick(self) -> None:
        """Один проход: замолчавшие → offline, очнувшиеся → закрыть алерт."""
        silenced = await self._health.mark_silent_nodes(
            stale_after_seconds=self._stale_after_sec,
        )
        for node_id in silenced:
            loguru.logger.warning("SilenceMonitor: узел {} переведён в offline", node_id)
        recovered = await self._health.resolve_recovered_nodes()
        for node_id in recovered:
            loguru.logger.info("SilenceMonitor: узел {} снова online, алерт закрыт", node_id)

    async def run(self) -> None:
        """Фоновый цикл. Первая пауза — чтобы тестовый lifespan не гонял тик
        параллельно с TRUNCATE фикстур."""
        loguru.logger.info(
            "SilenceMonitor запущен (порог {} сек, опрос {} сек)",
            self._stale_after_sec,
            self._poll_interval_sec,
        )
        while True:
            await asyncio.sleep(self._poll_interval_sec)
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                loguru.logger.exception("SilenceMonitor: сбой тика")
