import spade

from agents.cows_analizer import CowsAnalyzer
from spatial_analysis.agents.spatial_analizer import SpatialAnalyzer

async def main():
    
    spatial_analyser = SpatialAnalyzer()
    await spatial_analyser.start(auto_register=True)
    print("spatial_analyser started")

    await spade.wait_until_finished(spatial_analyser)
    print("Agents finished")


if __name__ == "__main__":
    spade.run(main())
