#!/bin/bash
set -euo pipefail

# Repology MCP Server Docker Runner
# This script makes it easy to run the Repology MCP server in different modes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="repology-mcp-server"
CONTAINER_NAME="repology-mcp"

usage() {
    cat << EOF
Usage: $0 [OPTIONS] COMMAND

Run Repology MCP Server in Docker

COMMANDS:
    build           Build the Docker image
    stdio           Run with stdio transport (for MCP clients)
    http            Run with HTTP transport on port 8000
    sse             Run with SSE transport on port 8001
    shell           Open a shell in the container
    logs            Show container logs
    stop            Stop and remove the container
    clean           Remove container and image

OPTIONS:
    -p, --port PORT     Port for HTTP/SSE transport (default: 8000 for HTTP, 8001 for SSE)
    -h, --help          Show this help message

EXAMPLES:
    $0 build                    # Build the image
    $0 stdio                    # Run with stdio (pipe input/output)
    $0 http                     # Run HTTP server on port 8000
    $0 http -p 9000             # Run HTTP server on port 9000
    $0 sse                      # Run SSE server on port 8001
    
    # For Claude Desktop, use stdio mode:
    echo '{"method": "initialize", ...}' | $0 stdio

EOF
}

build_image() {
    echo "🔨 Building Docker image..."
    docker build -t "$IMAGE_NAME" "$SCRIPT_DIR"
    echo "✅ Image built successfully"
}

run_stdio() {
    echo "🚀 Starting Repology MCP Server (stdio)..."
    docker run --rm -i \
        --name "$CONTAINER_NAME-stdio" \
        "$IMAGE_NAME" \
        repology-mcp-server --transport stdio
}

run_http() {
    local port=${1:-8000}
    echo "🚀 Starting Repology MCP Server (HTTP) on port $port..."
    docker run --rm -d \
        --name "$CONTAINER_NAME-http" \
        -p "$port:$port" \
        "$IMAGE_NAME" \
        repology-mcp-server --transport http --host 0.0.0.0 --port "$port"
    
    echo "✅ Server started on http://localhost:$port"
    echo "📊 View logs: $0 logs"
    echo "🛑 Stop server: $0 stop"
}

run_sse() {
    local port=${1:-8001}
    echo "🚀 Starting Repology MCP Server (SSE) on port $port..."
    docker run --rm -d \
        --name "$CONTAINER_NAME-sse" \
        -p "$port:$port" \
        "$IMAGE_NAME" \
        repology-mcp-server --transport sse --host 0.0.0.0 --port "$port"
    
    echo "✅ Server started on http://localhost:$port"
    echo "📊 View logs: $0 logs"
    echo "🛑 Stop server: $0 stop"
}

open_shell() {
    echo "🐚 Opening shell in container..."
    docker run --rm -it \
        --name "$CONTAINER_NAME-shell" \
        --entrypoint /bin/bash \
        "$IMAGE_NAME"
}

show_logs() {
    echo "📊 Container logs:"
    docker logs -f "$CONTAINER_NAME-http" 2>/dev/null || \
    docker logs -f "$CONTAINER_NAME-sse" 2>/dev/null || \
    echo "❌ No running container found"
}

stop_container() {
    echo "🛑 Stopping containers..."
    docker stop "$CONTAINER_NAME-http" 2>/dev/null || true
    docker stop "$CONTAINER_NAME-sse" 2>/dev/null || true
    docker stop "$CONTAINER_NAME-stdio" 2>/dev/null || true
    echo "✅ Containers stopped"
}

clean_all() {
    echo "🧹 Cleaning up..."
    stop_container
    docker rmi "$IMAGE_NAME" 2>/dev/null || true
    echo "✅ Cleanup complete"
}

# Parse command line arguments
PORT=""
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        build|stdio|http|sse|shell|logs|stop|clean)
            COMMAND="$1"
            shift
            ;;
        *)
            echo "❌ Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    exit 1
fi

# Execute command
case "${COMMAND:-}" in
    build)
        build_image
        ;;
    stdio)
        run_stdio
        ;;
    http)
        run_http "${PORT:-8000}"
        ;;
    sse)
        run_sse "${PORT:-8001}"
        ;;
    shell)
        open_shell
        ;;
    logs)
        show_logs
        ;;
    stop)
        stop_container
        ;;
    clean)
        clean_all
        ;;
    *)
        echo "❌ No command specified"
        usage
        exit 1
        ;;
esac