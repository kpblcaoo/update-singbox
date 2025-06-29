#!/usr/bin/env python3
"""Schema generator for sboxmgr models.

Generates JSON schemas from Pydantic models for use in sbox-common.
Implements ADR-0016: Pydantic as Single Source of Truth for Validation and Schema Generation.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from sboxmgr.config.models import AppConfig, LoggingConfig, ServiceConfig, AppSettings
    from sboxmgr.subscription.models import ClientProfile, InboundProfile
    # Note: ExclusionList and ExclusionRule are dataclasses, not Pydantic models
    # They would need to be converted to Pydantic models to generate schemas
except ImportError as e:
    print(f"Error importing models: {e}")
    print("Make sure you're running from the project root and models are available")
    sys.exit(1)


def generate_schemas() -> Dict[str, Dict[str, Any]]:
    """Generate JSON schemas from Pydantic models.
    
    Returns:
        Dict mapping schema names to JSON schema dictionaries
    """
    schemas = {
        "sboxmgr-config": AppConfig.schema(),
        "logging-config": LoggingConfig.schema(),
        "service-config": ServiceConfig.schema(),
        "app-settings": AppSettings.schema(),
        "client-profile": ClientProfile.schema(),
        "inbound-profile": InboundProfile.schema(),
        # Note: ExclusionList and ExclusionRule are dataclasses, not Pydantic models
        # They would need to be converted to Pydantic models to generate schemas
    }
    
    return schemas


def save_schemas(schemas: Dict[str, Dict[str, Any]], output_dir: Path) -> None:
    """Save schemas to JSON files.
    
    Args:
        schemas: Dictionary of schema name to schema content
        output_dir: Directory to save schema files
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for name, schema in schemas.items():
        output_path = output_dir / f"{name}.schema.json"
        
        # Add metadata to schema
        schema_with_metadata = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": f"{name.replace('-', ' ').title()} Schema",
            "description": f"JSON schema for {name} generated from Pydantic models",
            "generator": "sboxmgr-schema-generator",
            "version": "1.0.0",
            **schema
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(schema_with_metadata, f, indent=2, ensure_ascii=False)
        
        print(f"Generated: {output_path}")


def main():
    """Main function to generate and save schemas."""
    print("Generating JSON schemas from Pydantic models...")
    
    try:
        # Generate schemas
        schemas = generate_schemas()
        
        # Determine output directory
        project_root = Path(__file__).parent.parent
        output_dir = project_root / "schemas"
        
        # Save schemas
        save_schemas(schemas, output_dir)
        
        print(f"\n✅ Successfully generated {len(schemas)} schemas in {output_dir}")
        print("\nGenerated schemas:")
        for name in schemas.keys():
            print(f"  - {name}.schema.json")
            
    except Exception as e:
        print(f"❌ Error generating schemas: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 