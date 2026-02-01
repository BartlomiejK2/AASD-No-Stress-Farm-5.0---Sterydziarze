import asyncio
import spade
from agents.spatial_analizer import SpatialAnalyzer

async def main():
    spatial_analyser = SpatialAnalyzer()

    while True:
        try:
            await spatial_analyser.start(auto_register=True)
            print("spatial_analyser started")
            break
        except Exception as e:
            print("XMPP not ready, retrying in 5s:", e)
            await asyncio.sleep(5)
            
    with open("/tmp/agent_ready", "w") as f:
        f.write("ready")
    await spade.wait_until_finished(spatial_analyser)
    print("Agents finished")

if __name__ == "__main__":
    spade.run(main())
