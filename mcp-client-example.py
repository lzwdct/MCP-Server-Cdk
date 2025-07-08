#!/usr/bin/env python3
"""
MCP Client Example for connecting to the Bedrock MCP Server

This script demonstrates how to connect to and interact with the MCP server
that integrates with Amazon Bedrock.

Usage:
    python mcp-client-example.py
"""

import asyncio
import json
import sys
from typing import Any, Dict

import mcp.types as types
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client


async def main():
    """Main function to demonstrate MCP client usage."""
    
    print("🚀 Starting MCP Client for Bedrock Integration")
    print("=" * 50)
    
    # Connect to MCP server (adjust command as needed for your deployment)
    server_params = [
        sys.executable,
        "mcp-server/main.py"
    ]
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                
                # Initialize the session
                await session.initialize()
                print("✅ Connected to MCP Server")
                
                # List available tools
                print("\n📋 Available Tools:")
                tools = await session.list_tools()
                for tool in tools.tools:
                    print(f"  • {tool.name}: {tool.description}")
                
                # List available resources
                print("\n📚 Available Resources:")
                resources = await session.list_resources()
                for resource in resources.resources:
                    print(f"  • {resource.name}: {resource.description}")
                
                # Example 1: Create an item
                print("\n🔧 Example 1: Creating an item")
                create_result = await session.call_tool(
                    "create_item",
                    {
                        "name": "MCP Test Item",
                        "description": "An item created via MCP protocol",
                        "category": "test",
                        "metadata": {"source": "mcp-client", "version": "1.0"}
                    }
                )
                print(f"Result: {create_result.content[0].text}")
                
                # Example 2: List items
                print("\n📋 Example 2: Listing items")
                list_result = await session.call_tool("list_items", {"limit": 10})
                items_data = json.loads(list_result.content[0].text)
                print(f"Found {len(items_data)} items")
                
                # Example 3: Chat with Bedrock
                print("\n🤖 Example 3: Chat with Bedrock AI")
                chat_result = await session.call_tool(
                    "bedrock_chat",
                    {
                        "message": "Explain what MCP (Model Context Protocol) is in simple terms.",
                        "model_id": "anthropic.claude-3-haiku-20240307-v1:0"
                    }
                )
                print(f"AI Response: {chat_result.content[0].text}")
                
                # Example 4: Analyze items with Bedrock
                if len(items_data) > 0:
                    print("\n📊 Example 4: Analyzing items with Bedrock")
                    analysis_result = await session.call_tool(
                        "bedrock_analyze_items",
                        {
                            "analysis_type": "summary",
                            "model_id": "anthropic.claude-3-haiku-20240307-v1:0"
                        }
                    )
                    print(f"Analysis: {analysis_result.content[0].text}")
                
                # Example 5: Read resources
                print("\n📖 Example 5: Reading resources")
                try:
                    items_resource = await session.read_resource("items://all")
                    print(f"Items resource: {items_resource.contents[0].text[:200]}...")
                    
                    models_resource = await session.read_resource("bedrock://models")
                    models_data = json.loads(models_resource.contents[0].text)
                    print(f"Available Bedrock models: {len(models_data)} models")
                    for model in models_data[:3]:  # Show first 3 models
                        print(f"  • {model['modelId']} ({model['providerName']})")
                except Exception as e:
                    print(f"Resource read error: {e}")
                
                print("\n✅ MCP Client demonstration completed!")
                
    except Exception as e:
        print(f"❌ Error connecting to MCP server: {e}")
        print("Make sure the MCP server is running and accessible.")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())