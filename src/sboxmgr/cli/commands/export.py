"""CLI command for configuration export (`sboxctl export`).

This module implements the unified export command that replaces the previous
run and dry-run commands. It generates configurations from subscriptions and
exports them to various formats while following ADR-0014 principles:
- sboxmgr only generates configurations
- sboxagent handles service management
- No direct service restart from sboxmgr
"""
import typer
import os
import json
import tempfile
from pathlib import Path
from typing import Optional, List

from sboxmgr.subscription.manager import SubscriptionManager
from sboxmgr.subscription.models import SubscriptionSource, PipelineContext
from sboxmgr.server.exclusions import load_exclusions
from sboxmgr.i18n.t import t
from sboxmgr.utils.env import get_template_file, get_config_file, get_backup_file
from sboxmgr.export.export_manager import ExportManager
from sboxmgr.agent import AgentBridge, AgentNotAvailableError, ClientType
from sboxmgr.config.validation import validate_config_file


def _validate_flag_combinations(
    dry_run: bool, 
    agent_check: bool, 
    validate_only: bool, 
    url: Optional[str]
) -> None:
    """Validate flag combinations for mutual exclusivity.
    
    Args:
        dry_run: Dry run mode flag
        agent_check: Agent check mode flag  
        validate_only: Validate only mode flag
        url: Subscription URL
        
    Raises:
        typer.Exit: If invalid flag combination detected
    """
    if dry_run and agent_check:
        typer.echo("❌ Error: --dry-run and --agent-check are mutually exclusive", err=True)
        raise typer.Exit(1)
    
    if validate_only and url:
        typer.echo("❌ Error: --validate-only cannot be used with subscription URL", err=True)
        raise typer.Exit(1)
        
    if validate_only and (dry_run or agent_check):
        typer.echo("❌ Error: --validate-only cannot be used with --dry-run or --agent-check", err=True)
        raise typer.Exit(1)


def _determine_output_format(output_file: str, format_flag: str) -> str:
    """Determine output format based on file extension and format flag.
    
    Args:
        output_file: Output file path
        format_flag: Format flag value (json, toml, auto)
        
    Returns:
        Determined format (json or toml)
    """
    if format_flag == "auto":
        ext = Path(output_file).suffix.lower()
        if ext == ".toml":
            return "toml"
        else:
            return "json"
    return format_flag


def _create_backup_if_needed(output_file: str, backup: bool) -> Optional[str]:
    """Create backup of existing config file if requested.
    
    Args:
        output_file: Path to output file
        backup: Whether to create backup
        
    Returns:
        Path to backup file if created, None otherwise
    """
    if not backup or not os.path.exists(output_file):
        return None
        
    backup_file = get_backup_file()
    if backup_file:
        import shutil
        shutil.copy2(output_file, backup_file)
        typer.echo(f"📦 Backup created: {backup_file}")
        return backup_file
    return None


def _run_agent_check(config_file: str, agent_check: bool) -> bool:
    """Run agent validation check if requested.
    
    Args:
        config_file: Path to configuration file
        agent_check: Whether to run agent checks
        
    Returns:
        True if check passed or skipped, False if failed
    """
    if not agent_check:
        return True
        
    try:
        bridge = AgentBridge()
        if not bridge.is_available():
            typer.echo("ℹ️  sboxagent not available - skipping external validation", err=True)
            return True
            
        # Validate config with agent
        response = bridge.validate(Path(config_file), client_type=ClientType.SING_BOX)
        
        if response.success:
            typer.echo("✅ External validation passed")
            if response.client_detected:
                typer.echo(f"   Detected client: {response.client_detected}")
            if response.client_version:
                typer.echo(f"   Client version: {response.client_version}")
            return True
        else:
            typer.echo("❌ External validation failed:", err=True)
            for error in response.errors:
                typer.echo(f"   • {error}", err=True)
            return False
                
    except AgentNotAvailableError:
        typer.echo("ℹ️  sboxagent not available - skipping external validation", err=True)
        return True
    except Exception as e:
        typer.echo(f"⚠️  Agent check failed: {e}", err=True)
        return False


def _generate_config_from_subscription(
    url: str,
    user_agent: Optional[str],
    no_user_agent: bool,
    format: str,
    debug: int,
    skip_version_check: bool
) -> dict:
    """Generate configuration from subscription URL.
    
    Args:
        url: Subscription URL
        user_agent: Custom User-Agent header
        no_user_agent: Disable User-Agent header
        format: Export format
        debug: Debug level
        skip_version_check: Skip version compatibility check
        
    Returns:
        Generated configuration dictionary
        
    Raises:
        typer.Exit: If subscription processing fails
    """
    try:
        if no_user_agent:
            ua = ""
        else:
            ua = user_agent
            
        source = SubscriptionSource(url=url, source_type="url_base64", user_agent=ua)
        mgr = SubscriptionManager(source)
        exclusions = load_exclusions(dry_run=True)
        context = PipelineContext(mode="default", debug_level=debug)
        user_routes: List[str] = []
        
        # Create ExportManager with selected format
        export_mgr = ExportManager(export_format=format)
        config = mgr.export_config(
            exclusions=exclusions, 
            user_routes=user_routes, 
            context=context, 
            export_manager=export_mgr, 
            skip_version_check=skip_version_check
        )
        
        if not config.success or not config.config or not config.config.get("outbounds"):
            typer.echo("❌ ERROR: No servers parsed from subscription", err=True)
            raise typer.Exit(1)
            
        return config.config
        
    except Exception as e:
        typer.echo(f"❌ {t('error.subscription_failed')}: {e}", err=True)
        raise typer.Exit(1)


def _write_config_to_file(config_data: dict, output_file: str, output_format: str) -> None:
    """Write configuration to output file in specified format.
    
    Args:
        config_data: Configuration data to write
        output_file: Output file path  
        output_format: Output format (json or toml)
        
    Raises:
        typer.Exit: If writing fails
    """
    try:
        # Ensure output directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            
        if output_format == "toml":
            import toml
            config_content = toml.dumps(config_data)
        else:
            config_content = json.dumps(config_data, indent=2, ensure_ascii=False)
            
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(config_content)
            
        typer.echo(f"✅ Configuration written to: {output_file}")
        
    except Exception as e:
        typer.echo(f"❌ {t('cli.error_config_update')}: {e}", err=True)
        raise typer.Exit(1)


def export(
    url: str = typer.Option(
        None, "-u", "--url", help=t("cli.url.help"),
        envvar=["SBOXMGR_URL", "SINGBOX_URL", "TEST_URL"]
    ),
    debug: int = typer.Option(0, "-d", "--debug", help=t("cli.debug.help")),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate configuration without saving"),
    output: str = typer.Option("config.json", "--output", help="Output file path (ignored in dry-run and agent-check modes)"),
    format: str = typer.Option("json", "--format", help="Output format: json, toml, auto"),
    validate_only: bool = typer.Option(False, "--validate-only", help="Only validate existing configuration file"),
    agent_check: bool = typer.Option(False, "--agent-check", help="Check configuration via sboxagent without saving"),
    backup: bool = typer.Option(False, "--backup", help="Create backup before overwriting existing file"),
    user_agent: str = typer.Option(None, "--user-agent", help="Override User-Agent for subscription fetcher"),
    no_user_agent: bool = typer.Option(False, "--no-user-agent", help="Do not send User-Agent header"),
    skip_version_check: bool = typer.Option(True, "--skip-version-check", help="Skip sing-box version compatibility check")
):
    """Export configuration with various modes.
    
    This unified command replaces the previous run and dry-run commands while
    following ADR-0014 principles. It generates configurations from subscriptions
    and exports them to various formats without managing services directly.
    
    Modes:
    - Default: Generate and save config to output file
    - --dry-run: Validate without saving (uses temporary file)  
    - --agent-check: Check via sboxagent without saving
    - --validate-only: Validate existing config file only
    
    Args:
        url: Subscription URL to fetch from
        debug: Debug verbosity level (0-2)
        dry_run: Validate configuration without saving
        output: Output file path (default: config.json)
        format: Output format (json, toml, auto)
        validate_only: Only validate existing configuration
        agent_check: Check via sboxagent without applying
        backup: Create backup before overwriting
        user_agent: Custom User-Agent header
        no_user_agent: Disable User-Agent header
        skip_version_check: Skip version compatibility check
        
    Raises:
        typer.Exit: On validation failure or processing errors
    """
    from logsetup.setup import setup_logging
    setup_logging(debug_level=debug)
    
    # Validate flag combinations
    _validate_flag_combinations(dry_run, agent_check, validate_only, url)
    
    # Handle validate-only mode
    if validate_only:
        config_file = output
        if not os.path.exists(config_file):
            typer.echo(f"❌ Configuration file not found: {config_file}", err=True)
            raise typer.Exit(1)
            
        try:
            validate_config_file(config_file)
            typer.echo(f"✅ Configuration is valid: {config_file}")
            raise typer.Exit(0)
        except typer.Exit:
            # Re-raise typer.Exit to preserve exit code
            raise  
        except Exception as e:
            typer.echo(f"❌ Configuration is invalid: {config_file}", err=True)
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)
    
    # URL is required for other modes
    if not url:
        typer.echo("❌ Error: Subscription URL is required (use -u/--url)", err=True)
        raise typer.Exit(1)
    
    # Determine output format
    output_format = _determine_output_format(output, format)
    
    # Generate configuration from subscription
    config_data = _generate_config_from_subscription(
        url, user_agent, no_user_agent, "singbox", debug, skip_version_check
    )
    
    # Handle dry-run mode
    if dry_run:
        typer.echo("🔍 " + t("cli.dry_run_mode"))
        with tempfile.NamedTemporaryFile("w+", suffix=f".{output_format}", delete=False) as tmp:
            temp_path = tmp.name
            if output_format == "toml":
                import toml
                tmp.write(toml.dumps(config_data))
            else:
                tmp.write(json.dumps(config_data, indent=2, ensure_ascii=False))
        
        try:
            validate_config_file(temp_path)
            typer.echo("✅ " + t("cli.dry_run_valid"))
            exit_code = 0
        except Exception as e:
            typer.echo(f"❌ {t('cli.config_invalid')}", err=True)
            typer.echo(f"Error: {e}", err=True)
            exit_code = 1
        finally:
            os.unlink(temp_path)
            typer.echo("🗑️  " + t("cli.temp_file_deleted"))
            
        raise typer.Exit(exit_code)
    
    # Handle agent-check mode
    if agent_check:
        typer.echo("🔍 Checking configuration via sboxagent...")
        with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as tmp:
            temp_path = tmp.name
            tmp.write(json.dumps(config_data, indent=2, ensure_ascii=False))
        
        try:
            success = _run_agent_check(temp_path, True)
            exit_code = 0 if success else 1
        finally:
            os.unlink(temp_path)
            typer.echo("🗑️  Temporary file deleted")
            
        raise typer.Exit(exit_code)
    
    # Default mode: Generate and save configuration
    # Create backup if requested
    backup_file = _create_backup_if_needed(output, backup)
    
    # Write configuration to file
    _write_config_to_file(config_data, output, output_format)
    
    # Note: Following ADR-0014, we do NOT restart services here
    # That's sboxagent's responsibility
    typer.echo("✅ " + t("cli.update_completed"))
    typer.echo("ℹ️  Note: Use sboxagent to apply configuration to services")


# Create Typer app for export commands
app = typer.Typer(help="Export configurations in standardized formats")
app.command()(export)