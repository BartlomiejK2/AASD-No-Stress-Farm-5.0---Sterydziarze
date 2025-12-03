import os
import asyncio
import spade
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour
from spade import wait_until_finished


class HelloAgent(Agent):
    class HelloBehaviour(OneShotBehaviour):
        async def run(self):
            print("Hello from SPADE in Docker!")
            await asyncio.sleep(1)
            print("Behaviour finished.")
            await self.agent.stop()

    async def setup(self):
        print("Agent setup complete.")
        self.add_behaviour(self.HelloBehaviour())


async def main():
    jid = os.getenv("SPADE_JID", "agent@server_hello")
    password = os.getenv("SPADE_PASSWORD", "secret")

    agent = HelloAgent(jid, password)
    await agent.start(auto_register=True)
    print(f"Agent started as {jid}")

    # czekamy, aż agent się zakończy (stop jest wołane w Behaviour.run)
    await wait_until_finished(agent)
    print("Agent stopped.")


if __name__ == "__main__":
    # UŻYWAMY spade.run zamiast asyncio.run
    spade.run(main())
