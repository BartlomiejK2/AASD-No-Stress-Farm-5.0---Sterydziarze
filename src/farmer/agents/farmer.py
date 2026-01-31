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
    def _safe_get(d, path, default=0):
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

        state_icon = "🟢 WŁĄCZ" if turn_on else "🔴 WYŁĄCZ"
        print(f"   >>> [AKCJA] {cow_name}: {effector} -> {state_icon} (Powód: {reason})")

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

        state_icon = "🟢 WŁĄCZ" if turn_on else "🔴 WYŁĄCZ"
        print(f"   >>> [AKCJA] {room_part_name}: {effector} -> {state_icon} (Powód: {reason})")

    # ---------- NARRACJA / TABELKI ----------
    def narrate_spatial(self, report: dict, ts: str | None) -> str:
        # Wyciągamy godzinę z timestampa dla czytelności
        time_str = ts.split("T")[1][:8] if ts else "??"

        lines = []
        lines.append(f"\n╔════════════════════ RAPORT BUDYNKÓW ({time_str}) ═════════════════════╗")
        lines.append(f"║ {'OBIEKT':<12} │ {'TEMP':<8} │ {'WILGOTNOŚĆ':<10} │ {'STAN':<18} ║")
        lines.append("╠══════════════╪══════════╪════════════╪════════════════════╣")

        for part_name, stats in report.items():
            t = self._safe_get(stats, ["temperature", "last"], 0)
            h = self._safe_get(stats, ["humidity", "last"], 0)

            # Analiza stanu do wyświetlenia
            t_val = float(t)
            h_val = float(h)
            alerts = []
            if t_val > 21.0: alerts.append("🔥 ZA CIEPŁO")
            if h_val > 53.0: alerts.append("💧 ZA WILGOTNO")

            status = ", ".join(alerts) if alerts else "✅ OK"

            lines.append(f"║ {part_name:<12} │ {t_val:>6.1f}°C │ {h_val:>9.1f}% │ {status:<18} ║")

        lines.append("╚══════════════╧══════════╧════════════╧════════════════════╝")
        return "\n".join(lines)

    def narrate_cows(self, report: dict, ts: str | None) -> str:
        time_str = ts.split("T")[1][:8] if ts else "??"

        lines = []
        lines.append(f"\n╔════════════════════ RAPORT STADA ({time_str}) ════════════════════════╗")
        lines.append(f"║ {'KROWA':<10} │ {'TEMP':<7} │ {'pH':<5} │ {'PULS':<5} │ {'AKT.':<5} │ {'DIAGNOZA':<17} ║")
        lines.append("╠════════════╪═════════╪═══════╪═══════╪═══════╪═══════════════════╣")

        for cow_name, stats in report.items():
            t = self._safe_get(stats, ["temperature", "last"], 0)
            ph = self._safe_get(stats, ["pH", "last"], 0)
            pul = self._safe_get(stats, ["pulse", "last"], 0)
            act = self._safe_get(stats, ["activity", "last"], 0)

            # Konwersja na float do warunków
            t_val = float(t)
            ph_val = float(ph)
            pul_val = float(pul)
            act_val = float(act)

            # Logika statusów (taka sama jak w sterowaniu)
            alerts = []
            if t_val > 40.0:
                alerts.append("🔥 GORĄCZKA")
            elif t_val > 39.0:
                alerts.append("☀️ PRZEGRZANIE")

            if pul_val > 90 and act_val > 0.2: alerts.append("💓 STRES")

            if ph_val < 6.0 and act_val > 0.2: alerts.append("🍔 GŁÓD")

            status = " ".join(alerts) if alerts else "✅ ZDROWA"
            # Skracamy status jeśli za długi
            if len(status) > 17: status = status[:14] + "..."

            lines.append(
                f"║ {cow_name:<10} │ {t_val:>5.1f}°C │ {ph_val:>4.2f} │ {pul_val:>5.0f} │ {act_val:>4.2f}  │ {status:<17} ║")

        lines.append("╚════════════╧═════════╧═══════╧═══════╧═══════╧═══════════════════╝")
        return "\n".join(lines)

    # ---------- Behaviours ----------
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

            # 1) WYNIK OD EFEKTORA
            if "status" in payload and "effector" in payload:
                status = payload.get("status")
                effector = payload.get("effector")
                ts = payload.get("timestamp")
                target = payload.get("cow_name") or payload.get("room_part_name") or "Nieznany"

                icon = "✅" if status == "SUCCESS" else "❌"
                print(f"[WYNIK {icon}] {target} -> {effector}: {status}")
                return

            # 2) RAPORTY OKRESOWE
            if payload.get("type") != "PERIODIC_REPORT":
                return

            sender = str(msg.sender)
            report = payload.get("report")
            ts = payload.get("timestamp")

            if "spatial-analyzer" in sender or "spacial-analyzer" in sender:
                self.agent.last_reports["spatial"] = report
                self.agent.last_sources["spatial"] = ts
                print(self.agent.narrate_spatial(report, ts))
                return

            if "cow-analyzer" in sender or "cows-analyzer" in sender:
                self.agent.last_reports["cow"] = report
                self.agent.last_sources["cow"] = ts
                print(self.agent.narrate_cows(report, ts))
                return

    class PeriodicControl(PeriodicBehaviour):
        async def run(self):
            # Tu nie musimy drukować "START CYKLU", bo tabelki będą się pojawiać i tak
            # print(f"[PeriodicControl] --- START CYKLU DECYZYJNEGO ---")

            # --- OBSŁUGA KRÓW ---
            cow_report = self.agent.last_reports.get("cow")
            if cow_report:
                for cow_name, stats in cow_report.items():
                    try:
                        t_last = float(stats["temperature"]["last"])
                        pulse_last = float(stats["pulse"]["last"])
                        act_last = float(stats["activity"]["last"])
                        ph_last = float(stats["pH"]["last"])

                        # 1. Zraszacz (Gorączka)
                        if t_last > 40.0:
                            await self.agent.send_cow_effector_request(
                                sender_behaviour=self, cow_name=cow_name, effector="sprinkler",
                                turn_on=True, reason=f"Gorączka {t_last:.1f}"
                            )
                        elif t_last < 39.0:
                            await self.agent.send_cow_effector_request(
                                sender_behaviour=self, cow_name=cow_name, effector="sprinkler",
                                turn_on=False, reason="Temp OK"
                            )

                        # 2. Wentylator (Przegrzanie)
                        if t_last > 39.0:
                            await self.agent.send_cow_effector_request(
                                sender_behaviour=self, cow_name=cow_name, effector="fan",
                                turn_on=True, reason=f"Przegrzanie {t_last:.1f}"
                            )
                        elif t_last < 38.0:
                            await self.agent.send_cow_effector_request(
                                sender_behaviour=self, cow_name=cow_name, effector="fan",
                                turn_on=False, reason="Temp OK"
                            )

                        # 3. Czochrało (Stres)
                        if pulse_last > 90 and act_last > 0.2:
                            await self.agent.send_cow_effector_request(
                                sender_behaviour=self, cow_name=cow_name, effector="brush",
                                turn_on=True, reason=f"Stres (Puls {pulse_last:.0f})"
                            )
                        elif pulse_last < 80:
                            await self.agent.send_cow_effector_request(
                                sender_behaviour=self, cow_name=cow_name, effector="brush",
                                turn_on=False, reason="Koniec stresu"
                            )

                        # 4. Podajnik (Głód)
                        if ph_last < 6.0 and act_last > 0.2:
                            await self.agent.send_cow_effector_request(
                                sender_behaviour=self, cow_name=cow_name, effector="feeder",
                                turn_on=True, reason=f"Głód (pH {ph_last:.2f})"
                            )
                        elif ph_last > 6.5:
                            await self.agent.send_cow_effector_request(
                                sender_behaviour=self, cow_name=cow_name, effector="feeder",
                                turn_on=False, reason="pH w normie"
                            )

                    except Exception as e:
                        continue

            # --- OBSŁUGA OBÓR ---
            spatial_report = self.agent.last_reports.get("spatial")
            if spatial_report:
                for room_part, stats in spatial_report.items():
                    try:
                        t_last = float(stats["temperature"]["last"])
                        h_last = float(stats["humidity"]["last"])

                        if t_last > 21.0 or h_last > 53.0:
                            reason_str = []
                            if t_last > 21.0: reason_str.append("Temp")
                            if h_last > 53.0: reason_str.append("Wilg")

                            await self.agent.send_room_effector_request(
                                sender_behaviour=self,
                                room_part_name=room_part,
                                effector="air_conditioner",
                                turn_on=True,
                                reason=f"Przekroczono: {', '.join(reason_str)}"
                            )
                        else:
                            await self.agent.send_room_effector_request(
                                sender_behaviour=self,
                                room_part_name=room_part,
                                effector="air_conditioner",
                                turn_on=False,
                                reason="Warunki OK"
                            )

                    except Exception as e:
                        continue

    async def setup(self):
        self.add_behaviour(self.ReceiveBehaviour())
        self.add_behaviour(self.PeriodicControl(period=20))
        print("[Farmer] 🚜 Agent rolnika gotowy do pracy.")