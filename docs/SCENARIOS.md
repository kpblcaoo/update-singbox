# SboxMgr - Complete Gherkin Scenarios (Fixed Version)

## Core Use Cases

### Feature: Configuration Export (sboxmgr responsibility)

#### Scenario: Standard configuration export
```gherkin
Given user has subscription URL "https://example.com/subscription.txt"
And sboxmgr is installed and configured
When user executes command "sboxctl export -u https://example.com/subscription.txt"
Then system loads subscription from URL
And system determines subscription format (base64, JSON, URI list)
And system parses servers from subscription
And system validates servers (type, address, port)
And system applies middleware processing
And system generates sing-box configuration
And system atomically writes configuration to "config.json"
And system outputs message "✅ Configuration written to: config.json"
```

#### Scenario: Export with custom User-Agent
```gherkin
Given user has subscription URL "https://example.com/subscription.txt"
When user executes command "sboxctl export -u https://example.com/subscription.txt --user-agent 'CustomAgent/1.0'"
Then system uses "CustomAgent/1.0" as User-Agent
And system loads subscription with specified User-Agent
And system processes subscription as usual
```

#### Scenario: Export without User-Agent
```gherkin
Given user has subscription URL "https://example.com/subscription.txt"
When user executes command "sboxctl export -u https://example.com/subscription.txt --no-user-agent"
Then system does NOT send User-Agent header
And system loads subscription without User-Agent
And system processes subscription as usual
```

#### Scenario: Export with backup
```gherkin
Given file "config.json" exists
When user executes command "sboxctl export -u https://example.com/subscription.txt --backup"
Then system creates backup of existing file
And system outputs message "📦 Backup created: /path/to/backup.json"
And system atomically writes new configuration
```

### Feature: Agent Validation (sboxagent responsibility)

#### Scenario: Configuration validation via sboxagent
```gherkin
Given user has subscription URL "https://example.com/subscription.txt"
And sboxagent is available in system
When user executes command "sboxctl export -u https://example.com/subscription.txt --agent-check"
Then system loads and processes subscription
And system generates temporary configuration
And system sends configuration to sboxagent for validation
And sboxagent validates configuration syntax
And sboxagent determines client type (sing-box, clash, etc.)
And sboxagent returns validation result
And system outputs validation result
And system does NOT save configuration to disk
```

#### Scenario: sboxagent unavailable
```gherkin
Given user has subscription URL "https://example.com/subscription.txt"
And sboxagent is NOT available in system
When user executes command "sboxctl export -u https://example.com/subscription.txt --agent-check"
Then system loads and processes subscription
And system outputs message "ℹ️  sboxagent not available - skipping external validation"
And system exits successfully
```

### Feature: Dry-run Mode (local validation)

#### Scenario: Validation without saving
```gherkin
Given user has subscription URL "https://example.com/subscription.txt"
When user executes command "sboxctl export -u https://example.com/subscription.txt --dry-run"
Then system loads and processes subscription
And system generates configuration
And system validates configuration locally
And system outputs validation result
And system does NOT save configuration to disk
```

### Feature: Existing File Validation

#### Scenario: Validate existing file
```gherkin
Given configuration file "config.json" exists
When user executes command "sboxctl export --validate-only --output config.json"
Then system loads configuration file
And system validates JSON syntax
And system checks configuration structure
And system outputs validation result
```

### Feature: Security and Path Validation

#### Scenario: Attempt to write to system directory without permissions
```gherkin
Given user does NOT have root privileges
When user executes command "sboxctl export -u https://example.com/subscription.txt --output /etc/config.json"
Then system checks directory write permissions
And system detects lack of write permissions
And system outputs error "❌ Error: /etc directory is not writable"
And system exits with error code
```

#### Scenario: Atomic configuration writing
```gherkin
Given user has subscription URL "https://example.com/subscription.txt"
When user executes command "sboxctl export -u https://example.com/subscription.txt"
Then system creates temporary file with configuration
And system validates temporary file content
And system atomically moves temporary file to target location
And system cleans up temporary files on error
```

#### Scenario: Protection against overwriting critical files
```gherkin
Given file "/etc/passwd" exists
When user executes command "sboxctl export -u https://example.com/subscription.txt --output /etc/passwd"
Then system checks path safety
And system detects attempt to overwrite system file
And system outputs security error
And system exits with error code
```

### Feature: Exclusion Management

#### Scenario: Add server to exclusions
```gherkin
Given user has subscription URL "https://example.com/subscription.txt"
And system loaded server list
When user executes command "sboxctl exclusions -u https://example.com/subscription.txt --add 1"
Then system adds server with index 1 to exclusions
And system atomically saves exclusions to file
And system outputs confirmation of addition
```

#### Scenario: Remove server from exclusions
```gherkin
Given user has subscription URL "https://example.com/subscription.txt"
And server with index 1 is in exclusions
When user executes command "sboxctl exclusions -u https://example.com/subscription.txt --remove 1"
Then system removes server with index 1 from exclusions
And system atomically saves updated exclusions
And system outputs confirmation of removal
```

#### Scenario: View exclusion list
```gherkin
When user executes command "sboxctl exclusions --view"
Then system loads exclusions file
And system outputs list of excluded servers
And system shows exclusion metadata (date, reason)
```

#### Scenario: Clear all exclusions
```gherkin
Given system has exclusions
When user executes command "sboxctl exclusions --clear"
Then system clears all exclusions
And system atomically saves empty exclusions file
And system outputs confirmation of clearing
```

#### Scenario: Interactive exclusion management (TUI)
```gherkin
Given user has subscription URL "https://example.com/subscription.txt"
When user executes command "sboxctl exclusions -u https://example.com/subscription.txt --interactive"
Then system loads server list
And system displays interactive TUI menu
And system shows numbered server list
And system allows list navigation (up/down arrows)
And system allows server selection (spacebar)
And system requests selection confirmation
And system applies selected exclusions
```

### Feature: Server Listing

#### Scenario: List all servers
```gherkin
Given user has subscription URL "https://example.com/subscription.txt"
When user executes command "sboxctl list-servers -u https://example.com/subscription.txt"
Then system loads subscription
And system parses all servers
And system displays server list with indices
And system shows protocol type for each server
And system shows address and port for each server
And system shows additional metadata (if available)
```

### Feature: Language Management

#### Scenario: View current language
```gherkin
When user executes command "sboxctl lang"
Then system determines current language (env > config > system > default)
And system outputs current language and source
And system shows list of available languages
And system shows language self-names
And system marks AI-translated languages [AI]
```

#### Scenario: Set language
```gherkin
When user executes command "sboxctl lang --set ru"
Then system checks availability of language "ru"
And system atomically saves choice to configuration file
And system outputs confirmation of setting
And system shows path to configuration file
```

#### Scenario: Bilingual output for system language
```gherkin
Given system language is not English
When user executes command "sboxctl lang"
Then system determines system language
And system shows help in English
And system shows help in system language
And system shows bilingual mode notification
```

### Feature: Configuration Management

#### Scenario: Dump configuration
```gherkin
When user executes command "sboxctl config dump"
Then system loads full configuration
And system resolves settings hierarchy (CLI > env > file > defaults)
And system outputs configuration in YAML format
And system shows all active settings
```

#### Scenario: Dump configuration in JSON
```gherkin
When user executes command "sboxctl config dump --format json"
Then system loads full configuration
And system outputs configuration in JSON format
And system shows all active settings
```

#### Scenario: Dump with environment information
```gherkin
When user executes command "sboxctl config dump --include-env-info"
Then system loads full configuration
And system determines environment information
And system outputs configuration
And system shows environment information
```

### Feature: Error Handling

#### Scenario: Unavailable subscription URL
```gherkin
Given subscription URL "https://invalid-url.com/subscription.txt" is unavailable
When user executes command "sboxctl export -u https://invalid-url.com/subscription.txt"
Then system attempts to load subscription
And system receives connection error
And system outputs clear error message
And system exits with error code
```

#### Scenario: Unsupported subscription format
```gherkin
Given subscription file contains unsupported format
When user executes command "sboxctl export -u file://subscription.txt"
Then system attempts to determine format
And system cannot find suitable parser
And system outputs unsupported format message
And system exits with error code
```

#### Scenario: Empty subscription
```gherkin
Given subscription contains no valid servers
When user executes command "sboxctl export -u https://example.com/empty.txt"
Then system loads subscription
And system parses data
And system finds no valid servers
And system outputs warning "❌ ERROR: No servers parsed from subscription"
And system exits with error code
```

#### Scenario: File size exceeded
```gherkin
Given subscription file exceeds size limit (2MB)
When user executes command "sboxctl export -u file://large_subscription.txt"
Then system checks file size
And system detects size limit exceeded
And system outputs size exceeded warning
And system aborts processing
```

#### Scenario: Unsupported URL scheme
```gherkin
Given user specified unsupported URL scheme
When user executes command "sboxctl export -u ftp://example.com/subscription.txt"
Then system checks URL scheme
And system detects unsupported scheme "ftp"
And system outputs error "unsupported scheme: ftp"
And system exits with error code
```

### Feature: Caching and Performance

#### Scenario: Repeated request with cache
```gherkin
Given user already loaded subscription "https://example.com/subscription.txt"
When user executes command "sboxctl export -u https://example.com/subscription.txt" again
Then system uses cached data
And system does not reload subscription
And system processes data faster
```

#### Scenario: Force cache refresh
```gherkin
Given user already loaded subscription "https://example.com/subscription.txt"
When user executes command "sboxctl export -u https://example.com/subscription.txt --force-reload"
Then system ignores cache
And system reloads subscription
And system updates cache with new data
```

### Feature: Multiple Format Support

#### Scenario: Base64 subscription
```gherkin
Given subscription is in base64 format
When user executes command "sboxctl export -u https://example.com/base64.txt"
Then system determines format as base64
And system uses Base64Parser
And system decodes data
And system parses servers from decoded data
```

#### Scenario: JSON subscription
```gherkin
Given subscription is in JSON format
When user executes command "sboxctl export -u https://example.com/json.txt"
Then system determines format as JSON
And system uses JSONParser
And system parses JSON structure
And system extracts servers from JSON
```

#### Scenario: URI List subscription
```gherkin
Given subscription is in URI list format
When user executes command "sboxctl export -u https://example.com/uris.txt"
Then system determines format as URI list
And system uses URIListParser
And system parses URI strings
And system extracts servers from URIs
```

### Feature: Multiple Protocol Support

#### Scenario: Shadowsocks servers
```gherkin
Given subscription contains Shadowsocks servers
When user executes command "sboxctl export -u https://example.com/ss.txt"
Then system parses Shadowsocks configurations
And system validates required fields (address, port, method, password)
And system generates sing-box outbound for Shadowsocks
```

#### Scenario: VMess servers
```gherkin
Given subscription contains VMess servers
When user executes command "sboxctl export -u https://example.com/vmess.txt"
Then system parses VMess configurations
And system validates required fields (address, port, UUID)
And system generates sing-box outbound for VMess
```

#### Scenario: WireGuard servers with falsy values
```gherkin
Given subscription contains WireGuard servers with mtu=0 and keepalive=false
When user executes command "sboxctl export -u https://example.com/wg.txt"
Then system parses WireGuard configurations
And system validates required fields (address, port, private_key, peer_public_key)
And system generates sing-box outbound for WireGuard
And system includes mtu=0 in configuration
And system includes keepalive=false in configuration
```

### Feature: Middleware Processing

#### Scenario: Geo-filtering
```gherkin
Given subscription contains servers from different countries
When user executes command "sboxctl export -u https://example.com/subscription.txt"
And geo-filtering is enabled
Then system applies geo-filter middleware
And system filters servers by geographical criteria
And system adds geo-metadata to servers
```

### Feature: Debugging and Diagnostics

#### Scenario: Debug level 0 (default)
```gherkin
Given user did not specify debug level
When user executes command "sboxctl export -u https://example.com/subscription.txt"
Then system does NOT output debug information
And system shows only basic messages
```

#### Scenario: Debug level 1 (information)
```gherkin
Given debug level 1 is enabled
When user executes command "sboxctl export -u https://example.com/subscription.txt -d 1"
Then system outputs User-Agent information
And system shows number of processed servers
And system shows selected parsers and exporters
```

#### Scenario: Debug level 2 (detailed debugging)
```gherkin
Given debug level 2 is enabled
When user executes command "sboxctl export -u https://example.com/subscription.txt -d 2"
Then system outputs subscription hash: "sha256: a1b2c3d4..."
And system shows server count at each stage
And system outputs server list hash: "[DEBUG][middleware] servers: 15, sha256: e5f6g7h8..."
And system shows detailed information for each pipeline stage
And system shows selected parsers and exporters
And system shows data hashes for change tracking
```

### Feature: Export to Multiple Formats

#### Scenario: Export to sing-box format
```gherkin
Given user wants export to sing-box format
When user executes command "sboxctl export -u https://example.com/subscription.txt --format json"
Then system uses SingboxExporter
And system generates sing-box configuration
And system includes all required outbounds (direct, block, dns-out)
And system creates proper JSON structure
```

#### Scenario: Export to Clash format
```gherkin
Given user wants export to Clash format
When user executes command "sboxctl export -u https://example.com/subscription.txt --format clash"
Then system uses ClashExporter
And system generates Clash configuration
And system adapts protocols for Clash
And system creates proper YAML structure
```

### Feature: Internationalization

#### Scenario: Switch to Russian language
```gherkin
Given system supports Russian language
When user executes command "SBOXMGR_LANG=ru sboxctl export -u https://example.com/subscription.txt"
Then system loads Russian translations
And system outputs messages in Russian
And system shows errors in Russian
```

### Feature: Plugins and Extensions

#### Scenario: Create plugin
```gherkin
Given user wants to create new parser
When user executes command "sboxctl plugin-template parser"
Then system generates parser template
And system creates basic class structure
And system adds necessary imports
And system creates example implementation
```

## Invalid Flag Combinations (CLI Validation)

### Feature: CLI Flag Validation

#### Scenario: Mutually exclusive flags --dry-run and --agent-check
```gherkin
When user executes command "sboxctl export -u https://example.com/subscription.txt --dry-run --agent-check"
Then system detects flag conflict
And system outputs error "❌ Error: --dry-run and --agent-check are mutually exclusive"
And system exits with error code
```

#### Scenario: --validate-only with subscription URL
```gherkin
When user executes command "sboxctl export --validate-only -u https://example.com/subscription.txt"
Then system detects invalid combination
And system outputs error "❌ Error: --validate-only cannot be used with subscription URL"
And system exits with error code
```

#### Scenario: --validate-only with --dry-run
```gherkin
When user executes command "sboxctl export --validate-only --dry-run"
Then system detects invalid combination
And system outputs error "❌ Error: --validate-only cannot be used with --dry-run or --agent-check"
And system exits with error code
```

## Fixes in This Version

1. **CLI validation verified** - removed invalid flag combinations
2. **Use cases separated** - sboxmgr (generation) vs sboxagent (validation)
3. **Security scenarios added** - atomic writing, permission checks, overwrite protection
4. **Debug levels detailed** - specific hashes and messages
5. **Interactive TUI described** - navigation, selection, confirmation
6. **ADR and security checklist considered** - atomic_write, validate_path_is_safe
7. **Falsy values fixed** - mtu=0, keepalive=false correctly processed

This Gherkin scenario now matches the actual sboxmgr architecture and covers all edge cases. 