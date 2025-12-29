import spade

from agents.cows_analizer import CowsAnalyzer
from agents.spacial_analizer import SpacialAnalyzer


async def main():
    cows_analyser = CowsAnalyzer()
    await cows_analyser.start(auto_register=True)
    print("cows_analyser started")

    spacial_analyser = SpacialAnalyzer()
    await spacial_analyser.start(auto_register=True)
    print("spacial_analyser started")

    with open("/tmp/agent_ready", "w") as f:
        f.write("ready")

    await spade.wait_until_finished(cows_analyser)
    print("Agents finished")


if __name__ == "__main__":
    spade.run(main())
