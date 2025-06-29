"""Orchestrated subscription commands for CLI.

This module provides CLI commands that use the Orchestrator facade instead
of directly calling manager classes. This eliminates code duplication and
ensures consistent behavior across all operations.
"""

import typer
import os
import json
import tempfile
from typing import Optional

from sboxmgr.core import Orchestrator
from sboxmgr.i18n.loader import LanguageLoader
from sboxmgr.i18n.t import t
from sboxmgr.utils.env import get_config_file, get_backup_file


def _create_orchestrator(debug_level: int = 0, fail_safe: bool = False) -> Orchestrator:
    """Create orchestrator instance.
    
    Args:
        debug_level: Debug verbosity level (0-2).
        fail_safe: Whether to use fail-safe mode.
        
    Returns:
        Orchestrator: Configured orchestrator instance.
    """
    return Orchestrator.create_default(debug_level=debug_level, fail_safe=fail_safe)


def _setup_user_agent(user_agent: Optional[str], no_user_agent: bool) -> Optional[str]:
    """Setup User-Agent header."""
    if no_user_agent:
        return ""
    return user_agent


def _validate_config_with_temp_file(config_json: str) -> tuple[bool, str]:
    """Validate configuration using temporary file."""
    from sboxmgr.config.generate import validate_config_file
    
    with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as tmp:
        temp_path = tmp.name
        tmp.write(config_json)
    
    try:
        valid, output = validate_config_file(temp_path)
        return valid, output
    finally:
        os.unlink(temp_path)


def run_orchestrated(
    url: str = typer.Option(..., "-u", "--url", help=t("cli.url.help")),
    debug: int = typer.Option(0, "-d", "--debug", help=t("cli.debug.help")),
    dry_run: bool = typer.Option(False, "--dry-run", help=t("cli.dry_run.help")),
    config_file: str = typer.Option(None, "--config-file", help=t("cli.config_file.help")),
    backup_file: str = typer.Option(None, "--backup-file", help=t("cli.backup_file.help")),
    user_agent: str = typer.Option(None, "--user-agent", help="Custom User-Agent header"),
    no_user_agent: bool = typer.Option(False, "--no-user-agent", help="Disable User-Agent"),
    format: str = typer.Option("singbox", "--format", help="Export format"),
    skip_version_check: bool = typer.Option(True, "--skip-version-check", help="Skip version check"),
    user_routes: str = typer.Option(None, "--user-routes", help="Comma-separated list of route tags to include"),
    exclusions: str = typer.Option(None, "--exclusions", help="Comma-separated list of servers to exclude")
):
    """Update configuration from subscription using Orchestrator.
    
    Args:
        url: Subscription URL to fetch from.
        debug: Debug verbosity level (0-2).
        dry_run: Validate configuration without saving.
        config_file: Output configuration file path.
        backup_file: Backup file path.
        user_agent: Custom User-Agent header.
        no_user_agent: Disable User-Agent header.
        format: Export format (singbox, clash, v2ray).
        skip_version_check: Skip version compatibility check.
        user_routes: Comma-separated route tags to include.
        exclusions: Comma-separated servers to exclude.
        
    Raises:
        typer.Exit: On validation failure or processing errors.
    """
    from logsetup.setup import setup_logging
    setup_logging(debug_level=debug)
    
    orchestrator = _create_orchestrator(debug_level=debug)
    ua = _setup_user_agent(user_agent, no_user_agent)
    
    # Parse user_routes and exclusions
    user_routes_list = [x.strip() for x in user_routes.split(",")] if user_routes else None
    exclusions_list = [x.strip() for x in exclusions.split(",")] if exclusions else None
    
    try:
        # Export configuration through orchestrator
        export_result = orchestrator.export_configuration(
            source_url=url,
            source_type="url_base64",
            export_format=format,
            skip_version_check=skip_version_check,
            user_agent=ua,
            user_routes=user_routes_list,
            exclusions=exclusions_list
        )
        
        if not export_result["success"]:
            typer.echo(f"ERROR: {export_result.get('error', 'Export failed')}", err=True)
            raise typer.Exit(1)
        
        config_json = json.dumps(export_result["config"], indent=2, ensure_ascii=False)
        
    except Exception as e:
        typer.echo(f"{t('error.subscription_failed')}: {e}", err=True)
        raise typer.Exit(1)
    
    # Handle dry run
    if dry_run:
        typer.echo(t("cli.dry_run_mode"))
        valid, output = _validate_config_with_temp_file(config_json)
        
        if valid:
            typer.echo(t("cli.dry_run_valid"))
        else:
            typer.echo(f"{t('cli.config_invalid')}\n{output}", err=True)
        
        typer.echo(t("cli.temp_file_deleted"))
        raise typer.Exit(0 if valid else 1)
    
    # Write configuration files
    config_file = config_file or get_config_file()
    backup_file = backup_file or get_backup_file()
    
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            f.write(config_json)
        
        if backup_file:
            import shutil
            shutil.copy2(config_file, backup_file)
        
        # Restart service
        try:
            from sboxmgr.service.manage import manage_service
            manage_service()
            if debug >= 1:
                typer.echo(t("cli.service_restart_completed"))
        except Exception as e:
            typer.echo(f"[WARN] Failed to restart service: {e}", err=True)
            
    except Exception as e:
        typer.echo(f"{t('cli.error_config_update')}: {e}", err=True)
        raise typer.Exit(1)
    
    typer.echo(t("cli.update_completed"))


def exclusions_orchestrated(
    action: str = typer.Argument(..., help="Action: add, remove, list, clear"),
    server_id: str = typer.Option(None, "--server", help="Server ID"),
    name: str = typer.Option(None, "--name", help="Name for exclusion"),
    reason: str = typer.Option(None, "--reason", help="Reason for exclusion"),
    debug: int = typer.Option(0, "-d", "--debug", help=t("cli.debug.help"))
):
    """Manage server exclusions using Orchestrator."""
    from logsetup.setup import setup_logging
    setup_logging(debug_level=debug)
    
    orchestrator = _create_orchestrator(debug_level=debug)
    
    try:
        result = orchestrator.manage_exclusions(
            action=action,
            server_id=server_id,
            name=name,
            reason=reason
        )
        
        if result["success"]:
            typer.echo(result["message"])
            
            if action == "list" and result["data"] and result["data"]["exclusions"]:
                typer.echo(f"\nExclusions ({result['data']['count']}):")
                for excl in result["data"]["exclusions"]:
                    typer.echo(f"  {excl.get('server_id', 'unknown')}")
                    if excl.get('name'):
                        typer.echo(f"    Name: {excl['name']}")
                    if excl.get('reason'):
                        typer.echo(f"    Reason: {excl['reason']}")
        else:
            typer.echo(f"ERROR: {result['message']}", err=True)
            raise typer.Exit(1)
        
    except Exception as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(1)


def dry_run_orchestrated(
    url: str = typer.Option(
        ..., "-u", "--url", help=t("cli.url.help"),
        envvar=["SBOXMGR_URL", "SINGBOX_URL", "TEST_URL"]
    ),
    debug: int = typer.Option(0, "-d", "--debug", help=t("cli.debug.help")),
    user_agent: str = typer.Option(None, "--user-agent", help="Override User-Agent for subscription fetcher"),
    no_user_agent: bool = typer.Option(False, "--no-user-agent", help="Do not send User-Agent header"),
    format: str = typer.Option("singbox", "--format", help="Export format: singbox, clash, v2ray"),
    skip_version_check: bool = typer.Option(True, "--skip-version-check", help="Skip version compatibility check"),
    user_routes: str = typer.Option(None, "--user-routes", help="Comma-separated list of route tags to include"),
    exclusions: str = typer.Option(None, "--exclusions", help="Comma-separated list of servers to exclude")
):
    """Validate subscription configuration without making changes (Orchestrated).
    
    Uses the Orchestrator facade to perform validation with consistent error
    handling and logging. This eliminates code duplication between run and
    dry-run operations.
    
    Args:
        url: Subscription URL to validate.
        debug: Debug verbosity level (0-2).
        user_agent: Custom User-Agent header.
        no_user_agent: Disable User-Agent header.
        format: Export format for validation.
        skip_version_check: Skip version compatibility check.
        user_routes: Comma-separated route tags to include.
        exclusions: Comma-separated servers to exclude.
        
    Raises:
        typer.Exit: Exit code 0 if valid, 1 if invalid.
    """
    # Simply call run_orchestrated with dry_run=True
    run_orchestrated(
        url=url,
        debug=debug,
        dry_run=True,
        user_agent=user_agent,
        no_user_agent=no_user_agent,
        format=format,
        skip_version_check=skip_version_check,
        user_routes=user_routes,
        exclusions=exclusions
    )


def list_servers_orchestrated(
    url: str = typer.Option(
        ..., "-u", "--url", help=t("cli.url.help"),
        envvar=["SBOXMGR_URL", "SINGBOX_URL", "TEST_URL"]
    ),
    debug: int = typer.Option(0, "-d", "--debug", help=t("cli.debug.help")),
    user_agent: str = typer.Option(None, "--user-agent", help="Override User-Agent"),
    no_user_agent: bool = typer.Option(False, "--no-user-agent", help="Disable User-Agent header"),
    format_output: str = typer.Option("table", "--format", help="Output format: table, json, yaml"),
    show_details: bool = typer.Option(False, "--details", help="Show detailed server information"),
    filter_protocol: str = typer.Option(None, "--protocol", help="Filter by protocol (vmess, vless, trojan, etc.)"),
    user_routes: str = typer.Option(None, "--user-routes", help="Comma-separated route tags to include"),
    exclusions: str = typer.Option(None, "--exclusions", help="Comma-separated servers to exclude")
):
    """List servers from subscription using Orchestrator facade.
    
    Retrieves and displays server information from subscription source with
    optional filtering and formatting. Uses Orchestrator for consistent
    error handling and pipeline processing.
    
    Args:
        url: Subscription URL to fetch from.
        debug: Debug verbosity level (0-2).
        user_agent: Custom User-Agent header.
        no_user_agent: Disable User-Agent header.
        format_output: Output format (table, json, yaml).
        show_details: Show detailed server information.
        filter_protocol: Filter servers by protocol type.
        user_routes: Comma-separated route tags to include.
        exclusions: Comma-separated servers to exclude.
        
    Raises:
        typer.Exit: On fetch or processing failure.
    """
    from logsetup.setup import setup_logging
    setup_logging(debug_level=debug)
    
    # Create orchestrator
    orchestrator = _create_orchestrator(debug_level=debug, fail_safe=False)
    
    # Parse CLI arguments
    ua = _setup_user_agent(user_agent, no_user_agent)
    user_routes_list = [x.strip() for x in user_routes.split(",")] if user_routes else None
    exclusions_list = [x.strip() for x in exclusions.split(",")] if exclusions else None
    
    try:
        # Get servers through orchestrator
        result = orchestrator.get_subscription_servers(
            url=url,
            source_type="url_base64",
            user_routes=user_routes_list,
            exclusions=exclusions_list,
            mode="default",
            force_reload=False,
            user_agent=ua
        )
        
        if not result.success or not result.config:
            typer.echo("ERROR: Failed to retrieve servers from subscription.", err=True)
            if result.errors:
                for error in result.errors:
                    typer.echo(f"  - {error}", err=True)
            raise typer.Exit(1)
        
        servers = result.config
        
        # Apply protocol filter if specified
        if filter_protocol:
            servers = [s for s in servers if s.get('type') == filter_protocol]
        
        # Display results
        if format_output == "json":
            import json
            typer.echo(json.dumps(servers, indent=2, ensure_ascii=False))
        elif format_output == "yaml":
            import yaml
            typer.echo(yaml.dump(servers, default_flow_style=False, allow_unicode=True))
        else:
            # Table format
            if not servers:
                typer.echo("No servers found matching criteria.")
                raise typer.Exit(0)
            
            typer.echo(f"Found {len(servers)} servers:")
            typer.echo("-" * 80)
            
            for i, server in enumerate(servers, 1):
                protocol = server.get('type', 'unknown')
                server_name = server.get('tag', f'server-{i}')
                server_addr = server.get('server', 'unknown')
                server_port = server.get('server_port', 'unknown')
                
                if show_details:
                    typer.echo(f"{i:3d}. [{protocol:8s}] {server_name}")
                    typer.echo(f"      Address: {server_addr}:{server_port}")
                    if 'uuid' in server:
                        typer.echo(f"      UUID: {server['uuid']}")
                    if 'password' in server:
                        typer.echo(f"      Password: {server['password'][:8]}...")
                    typer.echo()
                else:
                    typer.echo(f"{i:3d}. [{protocol:8s}] {server_name:30s} {server_addr}:{server_port}")
        
    except Exception as e:
        typer.echo(f"{t('error.subscription_failed')}: {e}", err=True)
        raise typer.Exit(1) 