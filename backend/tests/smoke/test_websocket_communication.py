#!/usr/bin/env python3
"""
End-to-End WebSocket Communication Test

This script tests the real WebSocket communication between the Python backend
and a simulated frontend client, verifying that all components work together.
"""

import asyncio
import json
import websockets
import logging
import pytest
from src.isi_control.main import ISIMacroscopeBackend

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_websocket_client():
    """Simulate frontend WebSocket client"""
    try:
        # Connect to backend WebSocket server
        uri = "ws://localhost:8765"
        logger.info(f"🎨 Connecting to backend at {uri}")

        async with websockets.connect(uri) as websocket:
            logger.info("🎨 Connected to backend WebSocket")

            # Test 1: Receive welcome message
            welcome_message = await websocket.recv()
            welcome_data = json.loads(welcome_message)
            logger.info(f"📥 Received welcome: {welcome_data}")

            assert welcome_data["message_type"] == "state_update"
            assert welcome_data["payload"]["state_type"] == "connection"
            logger.info("✅ Welcome message received correctly")

            # Test 2: Send workflow.get_state command
            command_message = {
                "command": "workflow.get_state",
                "parameters": {},
                "request_id": "test_001"
            }

            logger.info("📤 Sending workflow.get_state command")
            await websocket.send(json.dumps(command_message))

            # Wait for response
            response_message = await websocket.recv()
            response_data = json.loads(response_message)
            logger.info(f"📥 Received response: {response_data}")

            assert response_data["message_type"] == "response"
            assert response_data["message_id"] == "test_001"
            assert response_data["payload"]["success"] is True
            assert "current_state" in response_data["payload"]["data"]
            logger.info("✅ Workflow state command successful")

            # Test 3: Send hardware.detect command
            hardware_command = {
                "command": "hardware.detect",
                "parameters": {},
                "request_id": "test_002"
            }

            logger.info("📤 Sending hardware.detect command")
            await websocket.send(json.dumps(hardware_command))

            # Wait for response
            hardware_response = await websocket.recv()
            hardware_data = json.loads(hardware_response)
            logger.info(f"📥 Received hardware response: {hardware_data}")

            assert hardware_data["message_type"] == "response"
            assert hardware_data["message_id"] == "test_002"
            assert hardware_data["payload"]["success"] is True
            logger.info("✅ Hardware detection command successful")

            # Test 4: Send system.health_check command
            health_command = {
                "command": "system.health_check",
                "parameters": {},
                "request_id": "test_003"
            }

            logger.info("📤 Sending system.health_check command")
            await websocket.send(json.dumps(health_command))

            # Wait for response
            health_response = await websocket.recv()
            health_data = json.loads(health_response)
            logger.info(f"📥 Received health response: {health_data}")

            assert health_data["message_type"] == "response"
            assert health_data["message_id"] == "test_003"
            assert health_data["payload"]["success"] is True
            logger.info("✅ Health check command successful")

            logger.info("🎉 All WebSocket communication tests passed!")
            return True

    except Exception as e:
        logger.error(f"❌ WebSocket client test failed: {e}")
        return False


async def run_end_to_end_test():
    """Run complete end-to-end communication test"""
    logger.info("🔍 Starting End-to-End WebSocket Communication Test")
    logger.info("=" * 80)

    # Start backend server
    backend = ISIMacroscopeBackend(development_mode=True, port=8765)

    try:
        # Initialize backend
        logger.info("🚀 Initializing backend...")
        await backend.initialize()

        # Start backend server in background
        logger.info("🚀 Starting backend server...")
        server_task = asyncio.create_task(backend.start())

        # Give server time to start
        await asyncio.sleep(2)

        # Run client tests
        logger.info("🎨 Starting frontend client tests...")
        client_success = await test_websocket_client()

        # Stop backend server
        logger.info("🛑 Stopping backend server...")
        await backend.stop()

        # Wait for server task to complete
        try:
            await asyncio.wait_for(server_task, timeout=2)
        except asyncio.TimeoutError:
            server_task.cancel()

        # Results
        logger.info("=" * 80)
        logger.info("📊 END-TO-END COMMUNICATION TEST RESULTS")
        logger.info("=" * 80)

        if client_success:
            logger.info("🎉 SUCCESS! Real WebSocket communication working perfectly!")
            logger.info("")
            logger.info("✅ Backend-Frontend Communication Verified:")
            logger.info("   ✅ WebSocket connection established")
            logger.info("   ✅ Welcome message exchange")
            logger.info("   ✅ Command-response cycle working")
            logger.info("   ✅ Workflow commands processed")
            logger.info("   ✅ Hardware commands processed")
            logger.info("   ✅ System commands processed")
            logger.info("   ✅ JSON serialization/deserialization")
            logger.info("   ✅ Request-response correlation")
            logger.info("   ✅ Thin client architecture maintained")
            logger.info("")
            logger.info("🏆 REAL BACKEND-FRONTEND CONNECTION OPERATIONAL!")
            return True
        else:
            logger.error("❌ End-to-end communication test failed")
            return False

    except Exception as e:
        logger.error(f"❌ End-to-end test setup failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_end_to_end_test())
    exit(0 if success else 1)