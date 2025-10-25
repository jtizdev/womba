"""
Atlassian Connect lifecycle and UI module endpoints.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from loguru import logger

from src.storage.installation_store import InstallationStore
from src.models.installation import Installation
from src.api.middleware.jwt_auth import require_jwt
from src.api.utils.jira_context import JiraContext


router = APIRouter(prefix="/connect", tags=["connect"])
installation_store = InstallationStore()


# ============================================================================
# Pydantic Models
# ============================================================================

class LifecyclePayload(BaseModel):
    """Payload received from Jira during lifecycle events."""
    key: str
    clientKey: str
    publicKey: Optional[str] = None
    sharedSecret: str
    serverVersion: str
    pluginsVersion: str
    baseUrl: str
    productType: str
    description: str
    eventType: str


# ============================================================================
# Lifecycle Endpoints
# ============================================================================

@router.post("/installed")
async def installed(payload: LifecyclePayload):
    """
    Called when the app is installed in a Jira instance.
    
    Stores the installation credentials (clientKey, sharedSecret) for JWT validation.
    """
    try:
        logger.info(f"App installed in {payload.clientKey} ({payload.baseUrl})")
        
        # Create installation record
        installation = Installation(
            client_key=payload.clientKey,
            shared_secret=payload.sharedSecret,
            base_url=payload.baseUrl,
            product_type=payload.productType,
            description=payload.description,
            public_key=payload.publicKey,
            installed_at=datetime.now(),
            enabled=True
        )
        
        # Save installation
        success = installation_store.save_installation(installation)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save installation")
        
        logger.info(f"Successfully saved installation for {payload.clientKey}")
        
        return {"success": True, "message": "App installed successfully"}
        
    except Exception as e:
        logger.error(f"Failed to process installation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/uninstalled")
async def uninstalled(payload: LifecyclePayload):
    """
    Called when the app is uninstalled from a Jira instance.
    
    Removes the installation record and cleans up any stored data.
    """
    try:
        logger.info(f"App uninstalled from {payload.clientKey}")
        
        # Delete installation record
        success = installation_store.delete_installation(payload.clientKey)
        
        if not success:
            logger.warning(f"Installation {payload.clientKey} not found during uninstall")
        
        # TODO: Clean up any user data, settings, etc.
        
        logger.info(f"Successfully removed installation for {payload.clientKey}")
        
        return {"success": True, "message": "App uninstalled successfully"}
        
    except Exception as e:
        logger.error(f"Failed to process uninstallation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enabled")
async def enabled(payload: LifecyclePayload):
    """
    Called when the app is enabled in a Jira instance.
    """
    try:
        logger.info(f"App enabled in {payload.clientKey}")
        
        # Update enabled status
        success = installation_store.update_enabled_status(payload.clientKey, True)
        
        if not success:
            logger.warning(f"Installation {payload.clientKey} not found during enable")
        
        return {"success": True, "message": "App enabled successfully"}
        
    except Exception as e:
        logger.error(f"Failed to process enable: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disabled")
async def disabled(payload: LifecyclePayload):
    """
    Called when the app is disabled in a Jira instance.
    """
    try:
        logger.info(f"App disabled in {payload.clientKey}")
        
        # Update enabled status
        success = installation_store.update_enabled_status(payload.clientKey, False)
        
        if not success:
            logger.warning(f"Installation {payload.clientKey} not found during disable")
        
        return {"success": True, "message": "App disabled successfully"}
        
    except Exception as e:
        logger.error(f"Failed to process disable: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Issue Glance (Badge on Issue)
# ============================================================================

@router.get("/issue-glance")
async def issue_glance(
    request: Request,
    issueKey: str,
    context: JiraContext = Depends(require_jwt)
):
    """
    Returns data for the issue glance (badge showing test count).
    
    This appears as a small badge on every Jira issue.
    """
    try:
        # TODO: Query actual test count from Zephyr or local storage
        # For now, return mock data
        test_count = 0
        
        return {
            "label": {
                "value": f"{test_count} Tests" if test_count > 0 else "No Tests"
            },
            "status": {
                "type": "default" if test_count > 0 else "new"
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to load issue glance: {e}")
        return {
            "label": {"value": "Error"},
            "status": {"type": "error"}
        }


# ============================================================================
# Issue Panel (Side Panel on Issue View)
# ============================================================================

@router.get("/issue-panel", response_class=HTMLResponse)
async def issue_panel(
    request: Request,
    issueKey: str,
    projectKey: Optional[str] = None,
    context: JiraContext = Depends(require_jwt)
):
    """
    Returns HTML for the issue panel that appears on Jira issue view.
    
    This panel allows users to generate tests directly from the issue.
    """
    try:
        # Read the static HTML file
        import os
        from pathlib import Path
        
        static_dir = Path(__file__).parent.parent.parent / "web" / "static"
        html_path = static_dir / "issue-panel.html"
        
        if html_path.exists():
            with open(html_path, 'r') as f:
                html_content = f.read()
            
            # Inject context into HTML
            html_content = html_content.replace('{{issueKey}}', issueKey)
            html_content = html_content.replace('{{projectKey}}', projectKey or '')
            html_content = html_content.replace('{{baseUrl}}', context.base_url)
            
            return HTMLResponse(content=html_content)
        else:
            # Return a simple HTML if file doesn't exist yet
            return HTMLResponse(content=f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Womba Test Generator</title>
                    <script src="https://connect-cdn.atl-paas.net/all.js"></script>
                    <style>
                        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; }}
                        .container {{ max-width: 100%; }}
                        h2 {{ color: #172B4D; }}
                        button {{ background: #0052CC; color: white; border: none; padding: 10px 20px; border-radius: 3px; cursor: pointer; }}
                        button:hover {{ background: #0065FF; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h2>Womba Test Generator</h2>
                        <p>Issue: <strong>{issueKey}</strong></p>
                        <button onclick="generateTests()">Generate Tests</button>
                        <div id="status"></div>
                    </div>
                    <script>
                        function generateTests() {{
                            document.getElementById('status').innerHTML = 'Generating tests...';
                            // TODO: Call API
                        }}
                    </script>
                </body>
                </html>
            """)
            
    except Exception as e:
        logger.error(f"Failed to load issue panel: {e}")
        return HTMLResponse(content=f"<p>Error loading panel: {str(e)}</p>", status_code=500)


# ============================================================================
# Test Manager (Full Page)
# ============================================================================

@router.get("/test-manager", response_class=HTMLResponse)
async def test_manager(
    request: Request,
    projectKey: Optional[str] = None,
    context: JiraContext = Depends(require_jwt)
):
    """
    Returns HTML for the test manager full page.
    
    This is a general page accessible from Jira's top navigation.
    """
    try:
        return HTMLResponse(content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Womba Test Manager</title>
                <script src="https://connect-cdn.atl-paas.net/all.js"></script>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 40px; }}
                    h1 {{ color: #172B4D; }}
                </style>
            </head>
            <body>
                <h1>Womba Test Manager</h1>
                <p>Project: <strong>{projectKey or 'All Projects'}</strong></p>
                <p>Bulk test generation, RAG management, and history coming soon...</p>
            </body>
            </html>
        """)
    except Exception as e:
        logger.error(f"Failed to load test manager: {e}")
        return HTMLResponse(content=f"<p>Error: {str(e)}</p>", status_code=500)


# ============================================================================
# Admin Configuration (Admin Only)
# ============================================================================

@router.get("/admin", response_class=HTMLResponse)
async def admin_config(
    request: Request,
    context: JiraContext = Depends(require_jwt)
):
    """
    Returns HTML for the admin configuration page.
    
    Only accessible to Jira administrators.
    """
    try:
        return HTMLResponse(content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Womba Configuration</title>
                <script src="https://connect-cdn.atl-paas.net/all.js"></script>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 40px; }}
                    h1 {{ color: #172B4D; }}
                    .form-group {{ margin-bottom: 20px; }}
                    label {{ display: block; margin-bottom: 5px; font-weight: 600; }}
                    input {{ width: 100%; max-width: 500px; padding: 8px; border: 1px solid #DFE1E6; border-radius: 3px; }}
                    button {{ background: #0052CC; color: white; border: none; padding: 10px 20px; border-radius: 3px; cursor: pointer; }}
                    button:hover {{ background: #0065FF; }}
                </style>
            </head>
            <body>
                <h1>Womba Configuration</h1>
                <form id="config-form">
                    <div class="form-group">
                        <label>OpenAI API Key:</label>
                        <input type="password" name="openai_key" placeholder="sk-..." />
                    </div>
                    <div class="form-group">
                        <label>Zephyr API Token:</label>
                        <input type="password" name="zephyr_token" placeholder="..." />
                    </div>
                    <button type="submit">Save Configuration</button>
                </form>
                <p id="status"></p>
                <script>
                    document.getElementById('config-form').addEventListener('submit', function(e) {{
                        e.preventDefault();
                        document.getElementById('status').innerHTML = 'Configuration saved!';
                    }});
                </script>
            </body>
            </html>
        """)
    except Exception as e:
        logger.error(f"Failed to load admin config: {e}")
        return HTMLResponse(content=f"<p>Error: {str(e)}</p>", status_code=500)

