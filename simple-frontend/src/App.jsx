import { useState, useEffect } from 'react'
import {
  ThemeProvider,
  createTheme,
  CssBaseline,
  AppBar,
  Toolbar,
  Typography,
  Container,
  Grid,
  Card,
  CardContent,
  Button,
  TextField,
  Chip,
  Box,
  Alert,
  CircularProgress,
  Paper,
  Fab
} from '@mui/material'
import {
  Refresh as RefreshIcon,
  Add as AddIcon,
  Send as SendIcon,
  Storage as StorageIcon,
  SmartToy as BotIcon
} from '@mui/icons-material'

// Create Material-UI theme
const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
    background: {
      default: '#f5f5f5',
    },
  },
  typography: {
    h4: {
      fontWeight: 600,
    },
    h6: {
      fontWeight: 500,
    },
  },
})

// MCP Client for communicating with MCP server over HTTP
class MCPClient {
  constructor(baseUrl = '') {
    this.baseUrl = baseUrl;
    this.requestId = 0;
  }

  async sendRequest(method, params = null) {
    const request = {
      jsonrpc: "2.0",
      id: (++this.requestId).toString(),
      method: method,
      params: params
    };

    console.log('🚀 Sending MCP request:', request);

    const response = await fetch(`${this.baseUrl}/mcp`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    console.log('📨 MCP response:', result);

    if (result.error) {
      throw new Error(result.error.message || 'MCP request failed');
    }

    return result.result;
  }

  async listTools() {
    const result = await this.sendRequest('tools/list');
    return result.tools || [];
  }

  async callTool(name, args = {}) {
    const result = await this.sendRequest('tools/call', {
      name: name,
      arguments: args
    });
    return result.content || [];
  }

  async listResources() {
    const result = await this.sendRequest('resources/list');
    return result.resources || [];
  }

  async readResource(uri) {
    const result = await this.sendRequest('resources/read', { uri });
    return result.contents || [];
  }
}

function App() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [chatMessage, setChatMessage] = useState('');
  const [chatResponse, setChatResponse] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [tools, setTools] = useState([]);

  const mcpClient = new MCPClient();

  useEffect(() => {
    loadTools();
    loadItems();
  }, []);

  const loadTools = async () => {
    try {
      const availableTools = await mcpClient.listTools();
      setTools(availableTools);
      console.log('Available MCP tools:', availableTools);
    } catch (err) {
      console.error('Failed to load tools:', err);
    }
  };

  const loadItems = async () => {
    try {
      setLoading(true);
      const result = await mcpClient.callTool('list_items', { limit: 50 });
      
      if (result && result.length > 0) {
        // Parse the JSON response from the tool
        const itemsText = result[0].text;
        const itemsData = JSON.parse(itemsText);
        setItems(itemsData || []);
      } else {
        setItems([]);
      }
      
      setError(null);
    } catch (err) {
      console.error('Failed to load items:', err);
      setError(err.message);
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateItem = async () => {
    try {
      const result = await mcpClient.callTool('create_item', {
        name: `Test Item ${Date.now()}`,
        description: 'Created from pure MCP frontend',
        category: 'test',
        metadata: { source: 'mcp-frontend' }
      });
      
      console.log('Item created:', result);
      loadItems(); // Reload items
    } catch (err) {
      console.error('Failed to create item:', err);
      setError(err.message);
    }
  };

  const handleChat = async () => {
    if (!chatMessage.trim()) return;
    
    try {
      setChatLoading(true);
      const result = await mcpClient.callTool('bedrock_chat', {
        message: chatMessage,
        model_id: 'amazon.titan-text-express-v1'
      });
      
      if (result && result.length > 0) {
        setChatResponse(result[0].text);
        setChatMessage(''); // Clear input after sending
        
        // If the response indicates an item operation, refresh the list
        if (result[0].text.includes('✅ Successfully executed!')) {
          console.log('AI performed item operation, refreshing list...');
          setTimeout(() => loadItems(), 1000); // Small delay to ensure DB is updated
        }
      }
    } catch (err) {
      console.error('Failed to send chat:', err);
      setChatResponse(`Error: ${err.message}`);
    } finally {
      setChatLoading(false);
    }
  };


  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown';
    return new Date(dateString).toLocaleString();
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      
      {/* App Bar */}
      <AppBar position="static" elevation={2}>
        <Toolbar>
          <StorageIcon sx={{ mr: 2 }} />
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Pure MCP Server Dashboard
          </Typography>
          <Chip 
            label={`${items.length} Items | ${tools.length} Tools`} 
            color="secondary" 
            variant="outlined"
            sx={{ color: 'white', borderColor: 'white' }}
          />
        </Toolbar>
      </AppBar>

      <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
        {/* Status Alert */}
        {error ? (
          <Alert severity="error" sx={{ mb: 3 }}>
            <strong>MCP Connection Error:</strong> {error}
          </Alert>
        ) : (
          <Alert severity="success" sx={{ mb: 3 }}>
            <strong>Status:</strong> Connected to MCP Server via HTTP Bridge ✅
          </Alert>
        )}

        <Grid container spacing={4}>
          {/* Items Section */}
          <Grid item xs={12} lg={8}>
            <Paper elevation={3} sx={{ p: 3 }}>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
                <Typography variant="h4" component="h2" display="flex" alignItems="center">
                  <StorageIcon sx={{ mr: 1 }} />
                  MCP Database Items ({items.length})
                </Typography>
                <Box>
                  <Button
                    variant="outlined"
                    startIcon={<RefreshIcon />}
                    onClick={loadItems}
                    disabled={loading}
                    sx={{ mr: 1 }}
                  >
                    Refresh via MCP
                  </Button>
                  <Button
                    variant="contained"
                    startIcon={<AddIcon />}
                    onClick={handleCreateItem}
                    disabled={loading}
                  >
                    MCP Create Item
                  </Button>
                </Box>
              </Box>

              {loading ? (
                <Box display="flex" justifyContent="center" p={4}>
                  <CircularProgress />
                </Box>
              ) : items.length === 0 ? (
                <Box textAlign="center" p={4}>
                  <Typography variant="h6" color="text.secondary" gutterBottom>
                    No items found in MCP server
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Use MCP tools to create your first item
                  </Typography>
                </Box>
              ) : (
                <Grid container spacing={2}>
                  {items.map((item) => (
                    <Grid item xs={12} md={6} key={item.id}>
                      <Card elevation={2} sx={{ height: '100%' }}>
                        <CardContent>
                          <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
                            <Typography variant="h6" component="h3" sx={{ fontWeight: 600 }}>
                              {item.name || 'Unnamed Item'}
                            </Typography>
                            <Chip 
                              label={item.category || 'uncategorized'} 
                              size="small" 
                              color="primary"
                              variant="outlined"
                            />
                          </Box>
                          
                          <Typography variant="body2" color="text.secondary" paragraph>
                            {item.description || 'No description'}
                          </Typography>

                          {/* ID Display - Prominent */}
                          <Box sx={{ 
                            backgroundColor: '#f5f5f5', 
                            p: 1.5, 
                            borderRadius: 1, 
                            border: '1px solid #e0e0e0',
                            mb: 2 
                          }}>
                            <Typography variant="caption" display="block" color="text.secondary" gutterBottom>
                              MCP ITEM ID
                            </Typography>
                            <Typography 
                              variant="body2" 
                              sx={{ 
                                fontFamily: 'monospace', 
                                wordBreak: 'break-all',
                                fontSize: '0.85rem'
                              }}
                            >
                              {item.id}
                            </Typography>
                          </Box>

                          <Typography variant="caption" display="block" color="text.secondary">
                            Created: {formatDate(item.created_at)}
                          </Typography>
                          {item.updated_at !== item.created_at && (
                            <Typography variant="caption" display="block" color="text.secondary">
                              Updated: {formatDate(item.updated_at)}
                            </Typography>
                          )}
                        </CardContent>
                      </Card>
                    </Grid>
                  ))}
                </Grid>
              )}
            </Paper>
          </Grid>

          {/* MCP Tools Section */}
          <Grid item xs={12} lg={4}>
            <Paper elevation={3} sx={{ p: 3, mb: 3 }}>
              <Typography variant="h5" component="h2" gutterBottom>
                Available MCP Tools
              </Typography>
              <Box>
                {tools.map((tool) => (
                  <Chip 
                    key={tool.name}
                    label={tool.name}
                    size="small"
                    variant="outlined"
                    sx={{ mr: 1, mb: 1 }}
                  />
                ))}
              </Box>
            </Paper>

            <Paper elevation={3} sx={{ p: 3, height: 'fit-content' }}>
              <Typography variant="h5" component="h2" gutterBottom display="flex" alignItems="center">
                <BotIcon sx={{ mr: 1 }} />
                MCP AI Agent Chat
              </Typography>
              
              <Alert severity="info" sx={{ mb: 3 }}>
                <Typography variant="body2">
                  💡 Pure MCP Protocol! Try: "list all items", "create item name laptop", 
                  "delete item [paste ID]", "update item [ID] name newname"
                </Typography>
              </Alert>

              <Box sx={{ mb: 2 }}>
                <TextField
                  fullWidth
                  multiline
                  rows={3}
                  variant="outlined"
                  placeholder="Send MCP commands via AI agent..."
                  value={chatMessage}
                  onChange={(e) => setChatMessage(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleChat();
                    }
                  }}
                  disabled={chatLoading}
                />
                <Box display="flex" justifyContent="flex-end" mt={1}>
                  <Button
                    variant="contained"
                    endIcon={chatLoading ? <CircularProgress size={16} /> : <SendIcon />}
                    onClick={handleChat}
                    disabled={!chatMessage.trim() || chatLoading}
                  >
                    {chatLoading ? 'MCP Processing...' : 'Send MCP'}
                  </Button>
                </Box>
              </Box>

              {chatResponse && (
                <Paper 
                  elevation={1} 
                  sx={{ 
                    p: 2, 
                    backgroundColor: '#fafafa',
                    border: '1px solid #e0e0e0'
                  }}
                >
                  <Typography variant="subtitle2" gutterBottom color="primary">
                    MCP AI Response:
                  </Typography>
                  <Typography 
                    variant="body2" 
                    sx={{ 
                      whiteSpace: 'pre-wrap',
                      fontFamily: chatResponse.includes('✅') ? 'inherit' : 'monospace'
                    }}
                  >
                    {chatResponse}
                  </Typography>
                </Paper>
              )}
            </Paper>
          </Grid>
        </Grid>
      </Container>

      {/* Floating Action Button for Quick MCP Create */}
      <Fab
        color="primary"
        aria-label="mcp-add"
        sx={{
          position: 'fixed',
          bottom: 16,
          right: 16,
        }}
        onClick={handleCreateItem}
      >
        <AddIcon />
      </Fab>
    </ThemeProvider>
  );
}

export default App;