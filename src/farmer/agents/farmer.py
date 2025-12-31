import os
import json
from datetime import datetime, timedelta
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, PeriodicBehaviour
from spade.message import Message


class FarmerAgent(Agent):
    def __init__(self):
        super().__init__("farmer@xmpp_server", os.getenv("PASSWORD"))

        self.last_reports = {"spatial": None, "cow": None}
        self.last_sources = {"spatial": None, "cow": None}

        self.last_command = {}
        self.command_log = []

    @staticmethod
    def _fmt_num(x, digits=1):
        try:
            return f"{float(x):.{digits}f}"
        except Exception:
            return str(x)

    @staticmethod
    def _safe_get(d, path, default=None):
        cur = d
        for p in path:
            if not isinstance(cur, dict) or p not in cur:
                return default
            cur = cur[p]
        return cur

    def _should_send(self, key, desired_on: bool, cooldown_s: int = 30) -> bool:
        now = datetime.utcnow()
        prev = self.last_command.get(key)
        if not prev:
            self.last_command[key] = {"turn_on": desired_on, "ts": now}
            return True

        same_state = (prev["turn_on"] == desired_on)
        dt = (now - prev["ts"]).total_seconds()

        if same_state and dt < cooldown_s:
            return False

        self.last_command[key] = {"turn_on": desired_on, "ts": now}
        return True

    async def send_cow_effector_request(self, sender_behaviour, cow_name: str, effector: str, turn_on: bool,
                                        reason: str):
        key = ("cow", cow_name, effector)
        if not self._should_send(key, bool(turn_on), cooldown_s=30):
            return

        msg = Message(to="cows-analyzer@xmpp_server")
        msg.set_metadata("performative", "request")
        msg.body = json.dumps({
            "type": "FARMER_EFFECTOR_REQUEST",
            "scope": "cow",
            "cow_name": cow_name,
            "effector": effector,
            "turn_on": bool(turn_on),
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        })

        await sender_behaviour.send(msg)

        event = {"kind": "CMD_SENT", "key": key, "turn_on": bool(turn_on), "reason": reason,
                 "ts": datetime.utcnow().isoformat()}
        self.command_log.append(event)
        print(f"[Farmer] CMD -> cows-analyzer: {cow_name} {effector} -> {turn_on} (reason={reason})")

    async def send_room_effector_request(self, sender_behaviour, room_part_name: str, effector: str, turn_on: bool,
                                         reason: str):
        key = ("room", room_part_name, effector)
        if not self._should_send(key, bool(turn_on), cooldown_s=30):
            return

        msg = Message(to="spacial-analyzer@xmpp_server")
        msg.set_metadata("performative", "request")
        msg.body = json.dumps({
            "type": "FARMER_EFFECTOR_REQUEST",
            "scope": "room",
            "room_part_name": room_part_name,
            "effector": effector,
            "turn_on": bool(turn_on),
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        })

        await sender_behaviour.send(msg)

        event = {"kind": "CMD_SENT", "key": key, "turn_on": bool(turn_on), "reason": reason,
                 "ts": datetime.utcnow().isoformat()}
        self.command_log.append(event)
        print(f"[Farmer] CMD -> spacial-analyzer: {room_part_name} {effector} -> {turn_on} (reason={reason})")
    def narrate_spatial(self, report: dict, ts: str | None) -> str:
        header = f"Raport obór{' @ ' + ts if ts else ''}:"
        if not report:
            return header + "\n- Brak danych."
        lines = [header]
        for part_name, stats in report.items():
            t_last = self._safe_get(stats, ["temperature", "last"])
            h_last = self._safe_get(stats, ["humidity", "last"])
            lines.append(f"- {part_name}: temp {self._fmt_num(t_last, 1)}°C, wilg {self._fmt_num(h_last, 1)}%")
        return "\n".join(lines)

    def narrate_cows(self, report: dict, ts: str | None) -> str:
        header = f"Raport krów{' @ ' + ts if ts else ''}:"
        if not report:
            return header + "\n- Brak danych."
        lines = [header]
        for cow_name, stats in report.items():
            t_last = self._safe_get(stats, ["temperature", "last"])
            ph_last = self._safe_get(stats, ["pH", "last"])
            act_last = self._safe_get(stats, ["activity", "last"])
            pulse_last = self._safe_get(stats, ["pulse", "last"])
            lines.append(
                f"- {cow_name}: temp {self._fmt_num(t_last, 1)}°C, pH {self._fmt_num(ph_last, 2)}, "
                f"act {self._fmt_num(act_last, 2)}, pulse {self._fmt_num(pulse_last, 0)}"
            )
        return "\n".join(lines)

    class ReceiveBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=15)
            if not msg:
                return


            perf = msg.get_metadata("performative")
            if perf != "inform":
                return

            try:
                payload = json.loads(msg.body) if msg.body else {}
            except Exception:
                return

            if "status" in payload and "effector" in payload:
                status = payload.get("status")
                effector = payload.get("effector")
                ts = payload.get("timestamp")

                if "cow_name" in payload:
                    cow_name = payload.get("cow_name")
                    print(f"[Farmer] RESULT cow={cow_name} effector={effector} status={status} @ {ts}")
                    self.agent.command_log.append(
                        {"kind": "CMD_RESULT", "scope": "cow", "target": cow_name, "effector": effector,
                         "status": status, "ts": ts, "details": payload.get("details")})
                    return

                if "room_part_name" in payload:
                    rp = payload.get("room_part_name")
                    print(f"[Farmer] RESULT room={rp} effector={effector} status={status} @ {ts}")
                    self.agent.command_log.append(
                        {"kind": "CMD_RESULT", "scope": "room", "target": rp, "effector": effector, "status": status,
                         "ts": ts, "details": payload.get("details")})
                    return

            if payload.get("type") != "PERIODIC_REPORT":
                return

            sender = str(msg.sender)
            report = payload.get("report")
            ts = payload.get("timestamp")

            if "spatial-analyzer@" in sender or "spacial-analyzer@" in sender:
                self.agent.last_reports["spatial"] = report
                self.agent.last_sources["spatial"] = ts
                print(self.agent.narrate_spatial(report, ts))
                return

            if "cow-analyzer@" in sender or "cows-analyzer@" in sender:
                self.agent.last_reports["cow"] = report
                self.agent.last_sources["cow"] = ts
                print(self.agent.narrate_cows(report, ts))
                return

    class PeriodicControl(PeriodicBehaviour):
        async def run(self):
            print(f"[PeriodicControl] --- START CYKLU DECYZYJNEGO @ {datetime.utcnow().time()} ---")

            cow_report = self.agent.last_reports.get("cow")
            if cow_report:
                for cow_name, stats in cow_report.items():
                    try:
                        val_raw = stats["temperature"]["last"]
                        t_last = float(val_raw)

                        print(f"[PeriodicControl] {cow_name}: Temp={t_last:.2f} (Próg włączenia > 40.0)")

                        if t_last > 40.0:
                            print(f"[PeriodicControl] DECYZJA: Włączam zraszacz dla {cow_name}!")
                            await self.agent.send_cow_effector_request(
                                sender_behaviour=self,
                                cow_name=cow_name,
                                effector="sprinkler",
                                turn_on=True,
                                reason=f"auto: fever {t_last:.1f}"
                            )
                        elif t_last < 39.0:
                            print(f"[PeriodicControl] DECYZJA: Wyłączam zraszacz dla {cow_name}.")
                            await self.agent.send_cow_effector_request(
                                sender_behaviour=self,
                                cow_name=cow_name,
                                effector="sprinkler",
                                turn_on=False,
                                reason=f"auto: temp ok {t_last:.1f}"
                            )
                        else:
                            print(f"[PeriodicControl] {cow_name}: Temp w histerezie (39-40), bez zmian.")

                    except Exception as e:
                        print(f"[PeriodicControl] BŁĄD przy krowie {cow_name}: {e}")

            spatial_report = self.agent.last_reports.get("spatial")
            if spatial_report:
                for room_part, stats in spatial_report.items():
                    try:
                        t_last = float(stats["temperature"]["last"])
                        h_last = float(stats["humidity"]["last"])

                        print(f"[PeriodicControl] {room_part}: T={t_last:.1f}, H={h_last:.1f} (Progi: T>21 lub H>53)")

                        if t_last > 21.0 or h_last > 53.0:
                            reason_str = []
                            if t_last > 21.0: reason_str.append("Temp")
                            if h_last > 53.0: reason_str.append("Humidity")

                            print(f"[PeriodicControl] DECYZJA: Włączam AC dla {room_part} ({', '.join(reason_str)})")

                            await self.agent.send_room_effector_request(
                                sender_behaviour=self,
                                room_part_name=room_part,
                                effector="air_conditioner",
                                turn_on=True,
                                reason=f"auto: high {'/'.join(reason_str)}"
                            )
                        else:
                            print(f"[PeriodicControl] DECYZJA: Wyłączam AC dla {room_part}")
                            await self.agent.send_room_effector_request(
                                sender_behaviour=self,
                                room_part_name=room_part,
                                effector="air_conditioner",
                                turn_on=False,
                                reason="auto: conditions ok"
                            )

                    except Exception as e:
                        print(f"[PeriodicControl] BŁĄD przy pomieszczeniu {room_part}: {e}")

            print("[PeriodicControl] --- KONIEC CYKLU ---\n")

    async def setup(self):
        self.add_behaviour(self.ReceiveBehaviour())
        self.add_behaviour(self.PeriodicControl(period=20))
        print("[Farmer] ready")