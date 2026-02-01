import asyncio
import spade
from agents.cows_analizer import CowsAnalyzer


async def main():
    cows_analyser = CowsAnalyzer()

    # --- retry połączenia z XMPP ---
    while True:
        try:
            await cows_analyser.start(auto_register=True)
            print("cows_analyser started")
            break
        except Exception as e:
            print("XMPP not ready, retrying in 5s:", e)
            await asyncio.sleep(5)

    # --- sygnał gotowości (healthcheck) ---
    with open("/tmp/agent_ready", "w") as f:
        f.write("ready")

    # --- agent żyje dopóki system działa ---
    await spade.wait_until_finished(cows_analyser)
    print("Agents finished")


if __name__ == "__main__":
    spade.run(main())
