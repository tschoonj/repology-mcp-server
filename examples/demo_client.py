"""Example client script to test the Repology MCP server."""

import asyncio
import json
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def main():
    """Demonstrate usage of the Repology MCP server."""
    # Configure server parameters
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "repology-mcp-server"]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()
            
            print("🔍 Listing available tools...")
            tools = await session.list_tools()
            for tool in tools.tools:
                print(f"  • {tool.name}: {tool.description}")
            
            print("\n🔍 Searching for Firefox projects...")
            result = await session.call_tool(
                "search_projects", 
                arguments={"query": "firefox", "limit": 5}
            )
            print("Firefox projects:")
            if result.content:
                data = json.loads(result.content[0].text)
                for project_name in data.keys():
                    print(f"  • {project_name}")
            
            print("\n🔍 Getting detailed Firefox project info...")
            result = await session.call_tool(
                "get_project",
                arguments={"project_name": "firefox"}
            )
            if result.content:
                data = json.loads(result.content[0].text)
                if isinstance(data, list) and data:
                    pkg = data[0]
                    print(f"  • Repository: {pkg.get('repo')}")
                    print(f"  • Version: {pkg.get('version')}")
                    print(f"  • Status: {pkg.get('status')}")
                    print(f"  • Summary: {pkg.get('summary', 'N/A')}")
            
            print("\n🔍 Listing recent projects...")
            result = await session.call_tool(
                "list_projects",
                arguments={"limit": 3}
            )
            if result.content:
                data = json.loads(result.content[0].text)
                print("Recent projects:")
                for project_name in list(data.keys())[:3]:
                    print(f"  • {project_name}")
            
            print("\n✅ Demo completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())