import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

# MCP imports
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "mcp-items")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
bedrock = boto3.client('bedrock-runtime', region_name=AWS_REGION)
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

# Pure MCP server - no data models needed

# Initialize MCP Server
server = Server("mcp-bedrock-server")

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """List available resources."""
    return [
        types.Resource(
            uri="items://all",
            name="All Items",
            description="List all items in the database",
            mimeType="application/json",
        ),
        types.Resource(
            uri="bedrock://models",
            name="Bedrock Models",
            description="Available Amazon Bedrock models",
            mimeType="application/json",
        )
    ]

@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Read a specific resource."""
    if uri == "items://all":
        try:
            response = table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('type').eq('item'),
                Limit=100
            )
            items = response.get('Items', [])
            return json.dumps(items, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to read items: {e}")
            return json.dumps({"error": str(e)})
    
    elif uri == "bedrock://models":
        try:
            # List available Bedrock models
            bedrock_client = boto3.client('bedrock', region_name=AWS_REGION)
            response = bedrock_client.list_foundation_models()
            models = [
                {
                    "modelId": model["modelId"],
                    "modelName": model.get("modelName", ""),
                    "providerName": model.get("providerName", ""),
                    "inputModalities": model.get("inputModalities", []),
                    "outputModalities": model.get("outputModalities", [])
                }
                for model in response.get("modelSummaries", [])
            ]
            return json.dumps(models, indent=2)
        except Exception as e:
            logger.error(f"Failed to list Bedrock models: {e}")
            return json.dumps({"error": str(e)})
    
    else:
        raise ValueError(f"Unknown resource: {uri}")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="create_item",
            description="Create a new item in the database",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the item"},
                    "description": {"type": "string", "description": "Description of the item"},
                    "category": {"type": "string", "description": "Category of the item"},
                    "metadata": {"type": "object", "description": "Additional metadata"}
                },
                "required": ["name", "description", "category"]
            },
        ),
        types.Tool(
            name="list_items",
            description="List all items from the database",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "number", "description": "Maximum number of items to return", "default": 50}
                }
            },
        ),
        types.Tool(
            name="get_item",
            description="Get a specific item by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {"type": "string", "description": "ID of the item to retrieve"}
                },
                "required": ["item_id"]
            },
        ),
        types.Tool(
            name="delete_item",
            description="Delete an item by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {"type": "string", "description": "ID of the item to delete"}
                },
                "required": ["item_id"]
            },
        ),
        types.Tool(
            name="bedrock_chat",
            description="Chat with Amazon Bedrock AI models",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Message to send to the AI model"},
                    "model_id": {"type": "string", "description": "Bedrock model ID", "default": "amazon.titan-text-express-v1"}
                },
                "required": ["message"]
            },
        ),
        types.Tool(
            name="bedrock_analyze_items",
            description="Use Bedrock AI to analyze items in the database",
            inputSchema={
                "type": "object",
                "properties": {
                    "analysis_type": {"type": "string", "description": "Type of analysis to perform", "enum": ["summary", "categorization", "insights"]},
                    "model_id": {"type": "string", "description": "Bedrock model ID", "default": "amazon.titan-text-express-v1"}
                },
                "required": ["analysis_type"]
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls."""
    try:
        if name == "create_item":
            # Create item in DynamoDB
            item_id = str(uuid.uuid4())
            timestamp = int(datetime.now().timestamp())
            
            item_data = {
                'id': item_id,
                'name': arguments['name'],
                'description': arguments['description'],
                'category': arguments['category'],
                'metadata': arguments.get('metadata', {}),
                'timestamp': timestamp,
                'type': 'item',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            table.put_item(Item=item_data)
            return [types.TextContent(type="text", text=f"Successfully created item with ID: {item_id}")]
            
        elif name == "list_items":
            # List items from DynamoDB
            limit = arguments.get('limit', 50)
            response = table.scan(
                FilterExpression=boto3.dynamodb.conditions.Attr('type').eq('item'),
                Limit=limit
            )
            items = response.get('Items', [])
            return [types.TextContent(type="text", text=json.dumps(items, indent=2, default=str))]
            
        elif name == "get_item":
            # Get specific item
            item_id = arguments['item_id']
            response = table.get_item(Key={'id': item_id})
            item = response.get('Item')
            if item:
                return [types.TextContent(type="text", text=json.dumps(item, indent=2, default=str))]
            else:
                return [types.TextContent(type="text", text=f"Item with ID {item_id} not found")]
                
        elif name == "delete_item":
            # Delete item
            item_id = arguments['item_id']
            table.delete_item(Key={'id': item_id})
            return [types.TextContent(type="text", text=f"Successfully deleted item {item_id}")]
            
        elif name == "bedrock_chat":
            # Chat with Bedrock as an intelligent agent
            message = arguments['message']
            model_id = arguments.get('model_id', 'amazon.titan-text-express-v1')
            
            try:
                # Let Bedrock AI decide what actions to take and extract parameters
                system_prompt = """You are an AI that EXECUTES MCP tool calls. You MUST output JSON action directives for me to execute.

CRITICAL RULE: When users ask to create/delete/update items, you MUST output EXACTLY this JSON format on a new line:

{"action": "create_item", "params": {"name": "item_name", "description": "description", "category": "category"}}

EXAMPLES:
User: "create an item"
You: I'll create an item for you.
{"action": "create_item", "params": {"name": "New Item", "description": "User requested item", "category": "general"}}

User: "delete item abc-123"  
You: I'll delete that item.
{"action": "delete_item", "params": {"id": "abc-123"}}

RULES:
1. ALWAYS include the JSON action on a separate line
2. Use actual parameters from user's request
3. For create_item, if user doesn't specify details, use reasonable defaults
4. NEVER just describe actions - always output the JSON to execute them

User message: """

                full_message = system_prompt + message
                
                # Prepare the request based on model type
                if model_id.startswith('anthropic.'):
                    # Claude format
                    request_body = {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 1000,
                        "messages": [
                            {
                                "role": "user",
                                "content": full_message
                            }
                        ]
                    }
                else:
                    # Titan format (and other models)
                    request_body = {
                        "inputText": full_message,
                        "textGenerationConfig": {
                            "maxTokenCount": 1000,
                            "stopSequences": [],
                            "temperature": 0.7,
                            "topP": 0.9
                        }
                    }
                
                response = bedrock.invoke_model(
                    modelId=model_id,
                    body=json.dumps(request_body)
                )
                
                response_body = json.loads(response['body'].read())
                
                # Parse response based on model type
                if model_id.startswith('anthropic.'):
                    ai_response = response_body['content'][0]['text']
                else:
                    # Titan format
                    ai_response = response_body['results'][0]['outputText']
                
                # Check if AI wants to perform an action
                import re
                # More robust JSON extraction for multi-line JSON
                json_pattern = r'\{[^{}]*"action"[^{}]*"params"[^{}]*\{[^{}]*\}[^{}]*\}'
                action_match = re.search(json_pattern, ai_response, re.DOTALL)
                if action_match:
                    try:
                        json_str = action_match.group(0)
                        # Clean up any formatting issues
                        json_str = re.sub(r'\s+', ' ', json_str)  # Normalize whitespace
                        action_json = json.loads(json_str)
                        action = action_json.get('action')
                        params = action_json.get('params', {})
                        
                        if action == 'create_item':
                            # Execute the create item action
                            item_id = str(uuid.uuid4())
                            timestamp = int(datetime.now().timestamp())
                            
                            item_data = {
                                'id': item_id,
                                'name': params.get('name', 'AI Generated Item'),
                                'description': params.get('description', 'Item created by AI agent'),
                                'category': params.get('category', 'ai-created'),
                                'metadata': {'created_by': 'ai_agent'},
                                'timestamp': timestamp,
                                'type': 'item',
                                'created_at': datetime.now().isoformat(),
                                'updated_at': datetime.now().isoformat()
                            }
                            
                            table.put_item(Item=item_data)
                            
                            # Remove the JSON action from the response and add success message
                            clean_response = re.sub(json_pattern, '', ai_response, flags=re.DOTALL).strip()
                            success_message = f"\n\n✅ Successfully executed! Created item:\n- ID: {item_id}\n- Name: {item_data['name']}\n- Category: {item_data['category']}\n- Description: {item_data['description']}"
                            
                            return [types.TextContent(type="text", text=clean_response + success_message)]
                            
                        elif action == 'delete_item':
                            # Execute the delete item action
                            item_id = params.get('id') or params.get('item_id')
                            if not item_id:
                                return [types.TextContent(type="text", text="❌ Error: No item ID provided for deletion")]
                            
                            try:
                                # Get item first to check if it exists
                                response = table.get_item(Key={'id': item_id})
                                item = response.get('Item')
                                
                                if not item:
                                    # Item not found - suggest listing items first
                                    clean_response = re.sub(json_pattern, '', ai_response, flags=re.DOTALL).strip()
                                    error_message = f"\n\n❌ Error: Item with ID '{item_id}' not found in database.\n\nTo see available items with their correct IDs, please ask me to 'list all items' first."
                                    return [types.TextContent(type="text", text=clean_response + error_message)]
                                
                                # Delete the item
                                table.delete_item(Key={'id': item_id})
                                
                                clean_response = re.sub(json_pattern, '', ai_response, flags=re.DOTALL).strip()
                                success_message = f"\n\n✅ Successfully executed! Deleted item:\n- ID: {item_id}\n- Name: {item.get('name', 'Unknown')}\n- Category: {item.get('category', 'Unknown')}"
                                
                                return [types.TextContent(type="text", text=clean_response + success_message)]
                                
                            except Exception as delete_error:
                                return [types.TextContent(type="text", text=f"❌ Error deleting item: {str(delete_error)}")]
                        
                        elif action == 'update_item':
                            # Execute the update item action
                            item_id = params.get('id') or params.get('item_id')
                            if not item_id:
                                return [types.TextContent(type="text", text="❌ Error: No item ID provided for update")]
                            
                            try:
                                # Get existing item first
                                response = table.get_item(Key={'id': item_id})
                                if 'Item' not in response:
                                    return [types.TextContent(type="text", text=f"❌ Error: Item with ID {item_id} not found")]
                                
                                # Update fields
                                update_expression = "SET updated_at = :updated_at"
                                expression_values = {":updated_at": datetime.now().isoformat()}
                                
                                for key, value in params.items():
                                    if key not in ['id', 'item_id', 'type', 'created_at', 'timestamp'] and value:
                                        update_expression += f", {key} = :{key}"
                                        expression_values[f":{key}"] = value
                                
                                table.update_item(
                                    Key={'id': item_id},
                                    UpdateExpression=update_expression,
                                    ExpressionAttributeValues=expression_values
                                )
                                
                                # Get updated item
                                response = table.get_item(Key={'id': item_id})
                                updated_item = response['Item']
                                
                                clean_response = re.sub(json_pattern, '', ai_response, flags=re.DOTALL).strip()
                                success_message = f"\n\n✅ Successfully executed! Updated item:\n- ID: {item_id}\n- Name: {updated_item.get('name', 'Unknown')}\n- Category: {updated_item.get('category', 'Unknown')}\n- Description: {updated_item.get('description', 'Unknown')}"
                                
                                return [types.TextContent(type="text", text=clean_response + success_message)]
                                
                            except Exception as update_error:
                                return [types.TextContent(type="text", text=f"❌ Error updating item: {str(update_error)}")]
                        
                        elif action == 'list_items':
                            # Execute the list items action
                            try:
                                limit = params.get('limit', 50)
                                response = table.scan(
                                    FilterExpression=boto3.dynamodb.conditions.Attr('type').eq('item'),
                                    Limit=limit
                                )
                                items = response.get('Items', [])
                                
                                clean_response = re.sub(json_pattern, '', ai_response, flags=re.DOTALL).strip()
                                items_summary = f"\n\n✅ Successfully executed! Found {len(items)} items:\n"
                                for item in items[:10]:  # Show first 10 items
                                    items_summary += f"- {item.get('name', 'Unknown')} (ID: {item.get('id', 'Unknown')}, Category: {item.get('category', 'Unknown')})\n"
                                
                                if len(items) > 10:
                                    items_summary += f"... and {len(items) - 10} more items"
                                
                                return [types.TextContent(type="text", text=clean_response + items_summary)]
                                
                            except Exception as list_error:
                                return [types.TextContent(type="text", text=f"❌ Error listing items: {str(list_error)}")]
                            
                    except (json.JSONDecodeError, Exception) as e:
                        logger.error(f"Failed to parse or execute AI action: {e}")
                
                return [types.TextContent(type="text", text=ai_response)]
                
            except Exception as e:
                logger.error(f"Bedrock error: {e}")
                return [types.TextContent(type="text", text=f"Error communicating with Bedrock: {str(e)}")]
                
        elif name == "bedrock_analyze_items":
            # Analyze items using Bedrock
            analysis_type = arguments['analysis_type']
            model_id = arguments.get('model_id', 'amazon.titan-text-express-v1')
            
            try:
                # Get all items
                response = table.scan(
                    FilterExpression=boto3.dynamodb.conditions.Attr('type').eq('item'),
                    Limit=100
                )
                items = response.get('Items', [])
                
                # Prepare analysis prompt
                items_text = json.dumps(items, indent=2, default=str)
                
                if analysis_type == "summary":
                    prompt = f"Please provide a summary of these items: {items_text}"
                elif analysis_type == "categorization":
                    prompt = f"Please analyze and categorize these items: {items_text}"
                elif analysis_type == "insights":
                    prompt = f"Please provide insights and patterns from these items: {items_text}"
                else:
                    prompt = f"Please analyze these items: {items_text}"
                
                # Send to Bedrock
                if model_id.startswith('anthropic.'):
                    # Claude format
                    request_body = {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 2000,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    }
                else:
                    # Titan format
                    request_body = {
                        "inputText": prompt,
                        "textGenerationConfig": {
                            "maxTokenCount": 2000,
                            "stopSequences": [],
                            "temperature": 0.7,
                            "topP": 0.9
                        }
                    }
                
                response = bedrock.invoke_model(
                    modelId=model_id,
                    body=json.dumps(request_body)
                )
                
                response_body = json.loads(response['body'].read())
                
                # Parse response based on model type
                if model_id.startswith('anthropic.'):
                    ai_analysis = response_body['content'][0]['text']
                else:
                    # Titan format
                    ai_analysis = response_body['results'][0]['outputText']
                
                return [types.TextContent(type="text", text=ai_analysis)]
                
            except Exception as e:
                logger.error(f"Bedrock analysis error: {e}")
                return [types.TextContent(type="text", text=f"Error analyzing items with Bedrock: {str(e)}")]
        
        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]
            
    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        return [types.TextContent(type="text", text=f"Error executing tool {name}: {str(e)}")]

# MCP-over-HTTP Bridge for browser compatibility
import json as json_module
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MCP Message Models
class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[str] = None
    method: str
    params: Optional[dict] = None

class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[dict] = None

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/mcp")
async def handle_mcp_request(request: MCPRequest):
    """Handle MCP protocol messages over HTTP"""
    try:
        if request.method == "tools/list":
            # List available tools
            tools = await handle_list_tools()
            tools_dict = []
            for tool in tools:
                tools_dict.append({
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema
                })
            return MCPResponse(
                id=request.id,
                result={"tools": tools_dict}
            )
        
        elif request.method == "tools/call":
            # Call a specific tool
            if not request.params:
                raise HTTPException(status_code=400, detail="Missing params for tool call")
            
            tool_name = request.params.get("name")
            arguments = request.params.get("arguments", {})
            
            if not tool_name:
                raise HTTPException(status_code=400, detail="Missing tool name")
            
            result = await handle_call_tool(tool_name, arguments)
            content_dict = []
            for content in result:
                content_dict.append({
                    "type": content.type,
                    "text": content.text
                })
            return MCPResponse(
                id=request.id,
                result={"content": content_dict}
            )
        
        elif request.method == "resources/list":
            # List available resources
            resources = await handle_list_resources()
            resources_dict = []
            for resource in resources:
                resources_dict.append({
                    "uri": resource.uri,
                    "name": resource.name,
                    "description": resource.description,
                    "mimeType": resource.mimeType
                })
            return MCPResponse(
                id=request.id,
                result={"resources": resources_dict}
            )
        
        elif request.method == "resources/read":
            # Read a specific resource
            if not request.params:
                raise HTTPException(status_code=400, detail="Missing params for resource read")
            
            uri = request.params.get("uri")
            if not uri:
                raise HTTPException(status_code=400, detail="Missing resource URI")
            
            content = await handle_read_resource(uri)
            return MCPResponse(
                id=request.id,
                result={"contents": [{"uri": uri, "mimeType": "application/json", "text": content}]}
            )
        
        else:
            raise HTTPException(status_code=400, detail=f"Unknown method: {request.method}")
    
    except Exception as e:
        logger.error(f"MCP request error: {e}")
        return MCPResponse(
            id=request.id,
            error={"code": -32603, "message": str(e)}
        )

# Run MCP server on stdio
async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="mcp-bedrock-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    # Run MCP-over-HTTP bridge
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)