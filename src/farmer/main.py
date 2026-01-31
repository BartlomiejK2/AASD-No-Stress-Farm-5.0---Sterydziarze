import spade
from agents.farmer import FarmerAgent

async def main():
    farmer = FarmerAgent()
    await farmer.start(auto_register=True)

    with open("/tmp/agent_ready", "w") as f:
        f.write("ready")

    await spade.wait_until_finished(farmer)

if __name__ == "__main__":
    spade.run(main())
