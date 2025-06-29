import os
import shutil
import pytest
from typer.testing import CliRunner
from sboxmgr.cli import plugin_template
from sboxmgr.cli.plugin_template import plugin_template as plugin_template_func
import tempfile
from pathlib import Path
from unittest.mock import patch
import typer

runner = CliRunner()

ALL_TYPES = [
    "fetcher",
    "parser",
    "validator",
    "exporter",
    "postprocessor",
    "parsed_validator",
]

def clean_dir(path):
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)

def test_plugin_template_generates_all_types(tmp_path):
    output_dir = tmp_path / "plugin_templates"
    clean_dir(output_dir)
    for t in ALL_TYPES:
        name = f"Test{t.title().replace('_', '')}"
        result = runner.invoke(plugin_template.app, [t, name, "--output-dir", str(output_dir)])
        assert result.exit_code == 0, f"Failed for type {t}: {result.output}"
        py_file = output_dir / f"{name.lower()}.py"
        test_file = output_dir / f"template_test_{name.lower()}.py"
        assert py_file.exists(), f"{py_file} not created"
        assert test_file.exists(), f"{test_file} not created"
        # Проверяем docstring и импорты
        content = py_file.read_text(encoding="utf-8")
        assert '"""' in content, f"No docstring in {py_file}"
        assert "from" in content, f"No import in {py_file}"

def test_plugin_template_invalid_type(tmp_path):
    output_dir = tmp_path / "plugin_templates"
    clean_dir(output_dir)
    result = runner.invoke(plugin_template.app, ["invalidtype", "TestInvalid", "--output-dir", str(output_dir)])
    assert result.exit_code != 0
    assert "Type must be one of" in result.output

def test_plugin_template_output_dir_error(monkeypatch, tmp_path):
    # Симулируем ошибку создания директории
    def fail_makedirs(*a, **kw):
        raise OSError("fail")
    monkeypatch.setattr(os, "makedirs", fail_makedirs)
    result = runner.invoke(plugin_template.app, ["fetcher", "TestFetcher", "--output-dir", str(tmp_path / "fail_dir")])
    assert result.exit_code != 0
    assert "Failed to create output directory" in result.output

class TestPluginTemplate:
    """Test plugin_template function."""
    
    def test_plugin_template_fetcher(self, tmp_path):
        """Test plugin_template generates fetcher template."""
        output_dir = str(tmp_path / "test_output")
        
        with patch('typer.echo') as mock_echo:
            plugin_template_func(type="fetcher", name="Custom", output_dir=output_dir)
        
        # Check files were created
        plugin_file = Path(output_dir) / "custom.py"
        test_file = Path(output_dir) / "template_test_custom.py"
        
        assert plugin_file.exists()
        assert test_file.exists()
        
        # Check plugin file content
        content = plugin_file.read_text()
        assert "class CustomFetcher(BaseFetcher):" in content
        assert "from ..base_fetcher import BaseFetcher" in content
        assert "@register(\"custom_fetcher\")" in content
        assert "def fetch(self, force_reload: bool = False) -> bytes:" in content
        
        # Check test file content
        test_content = test_file.read_text()
        assert "from sboxmgr.subscription.fetchers.customfetcher import CustomFetcher" in test_content
        assert "plugin.fetch(None)" in test_content
        
        # Check echo calls
        mock_echo.assert_any_call(f"Created {plugin_file} and {test_file}")
    
    def test_plugin_template_parser(self, tmp_path):
        """Test plugin_template generates parser template."""
        output_dir = str(tmp_path / "test_output")
        plugin_template_func(type="parser", name="Custom", output_dir=output_dir)
        
        # Check files were created
        plugin_file = Path(output_dir) / "custom.py"
        test_file = Path(output_dir) / "template_test_custom.py"
        
        assert plugin_file.exists()
        assert test_file.exists()
        
        # Check plugin file content
        content = plugin_file.read_text()
        assert "class CustomParser(BaseParser):" in content
        assert "from ..base_parser import BaseParser" in content
        assert "@register(\"custom_parser\")" in content
        assert "def parse(self, raw: bytes) -> list[ParsedServer]:" in content
        
        # Check test file content
        test_content = test_file.read_text()
        assert "plugin.parse(b\"test\")" in test_content
    
    def test_plugin_template_validator(self, tmp_path):
        """Test plugin_template generates validator template."""
        output_dir = str(tmp_path / "test_output")
        plugin_template_func(type="validator", name="Custom", output_dir=output_dir)
        
        # Check files were created
        plugin_file = Path(output_dir) / "custom.py"
        test_file = Path(output_dir) / "template_test_custom.py"
        
        assert plugin_file.exists()
        assert test_file.exists()
        
        # Check plugin file content
        content = plugin_file.read_text()
        assert "class CustomValidator(BaseValidator):" in content
        assert "from ..validators.base import BaseValidator" in content
        assert "@register" not in content  # Validators don't use @register
        assert "def validate(self, raw: bytes, context=None):" in content
        
        # Check test file content
        test_content = test_file.read_text()
        assert "plugin.validate(b\"test\")" in test_content
    
    def test_plugin_template_parsed_validator(self, tmp_path):
        """Test plugin_template generates parsed validator template."""
        output_dir = str(tmp_path / "test_output")
        plugin_template_func(type="parsed_validator", name="Custom", output_dir=output_dir)
        
        # Check files were created
        plugin_file = Path(output_dir) / "custom.py"
        test_file = Path(output_dir) / "template_test_custom.py"
        
        assert plugin_file.exists()
        assert test_file.exists()
        
        # Check plugin file content
        content = plugin_file.read_text()
        assert "class CustomParsedValidator(BaseParsedValidator):" in content
        assert "from ..validators.base import BaseParsedValidator" in content
        assert "@register_parsed_validator(\"custom_parsed_validator\")" in content
        assert "def validate(self, servers: list[ParsedServer], context):" in content
        
        # Check test file content
        test_content = test_file.read_text()
        assert "plugin.validate(b\"test\", None)" in test_content
    
    def test_plugin_template_exporter(self, tmp_path):
        """Test plugin_template generates exporter template."""
        output_dir = str(tmp_path / "test_output")
        plugin_template_func(type="exporter", name="Custom", output_dir=output_dir)
        
        # Check files were created
        plugin_file = Path(output_dir) / "custom.py"
        test_file = Path(output_dir) / "template_test_custom.py"
        
        assert plugin_file.exists()
        assert test_file.exists()
        
        # Check plugin file content
        content = plugin_file.read_text()
        assert "class CustomExporter(BaseExporter):" in content
        assert "from ..base_exporter import BaseExporter" in content
        assert "@register(\"custom_exporter\")" in content
        assert "def export(self, servers: list[ParsedServer]) -> dict:" in content
        
        # Check test file content
        test_content = test_file.read_text()
        assert "plugin.export([])" in test_content
    
    def test_plugin_template_postprocessor(self, tmp_path):
        """Test plugin_template generates postprocessor template."""
        output_dir = str(tmp_path / "test_output")
        plugin_template_func(type="postprocessor", name="Custom", output_dir=output_dir)
        
        # Check files were created
        plugin_file = Path(output_dir) / "custom.py"
        test_file = Path(output_dir) / "template_test_custom.py"
        
        assert plugin_file.exists()
        assert test_file.exists()
        
        # Check plugin file content
        content = plugin_file.read_text()
        assert "class CustomPostProcessor(BasePostProcessor):" in content
        assert "from ..postprocessor_base import BasePostProcessor" in content
        assert "@register(\"custom_postprocessor\")" in content
        assert "def process(self, servers: list[ParsedServer], context) -> list[ParsedServer]:" in content
        
        # Check test file content
        test_content = test_file.read_text()
        assert "plugin.process([], None)" in test_content
    
    def test_plugin_template_invalid_type(self, tmp_path):
        """Test plugin_template handles invalid type."""
        output_dir = str(tmp_path / "test_output")
        
        with patch('typer.echo') as mock_echo:
            with pytest.raises(typer.Exit) as exc_info:
                plugin_template_func(type="invalid", name="Custom", output_dir=output_dir)
        
        assert exc_info.value.exit_code == 1
        # Check that error message was called with err=True
        assert any(call.kwargs.get('err') for call in mock_echo.call_args_list)
        # Check that message contains expected types
        error_msg = mock_echo.call_args_list[-1].args[0]
        assert "Type must be one of:" in error_msg
        assert "fetcher" in error_msg
        assert "parser" in error_msg
    
    def test_plugin_template_case_insensitive_type(self, tmp_path):
        """Test plugin_template handles case insensitive type."""
        output_dir = str(tmp_path / "test_output")
        plugin_template_func(type="FETCHER", name="Custom", output_dir=output_dir)
        
        # Should work and create fetcher template
        plugin_file = Path(output_dir) / "custom.py"
        assert plugin_file.exists()
        
        content = plugin_file.read_text()
        assert "class CustomFetcher(BaseFetcher):" in content
    
    def test_plugin_template_name_already_has_suffix(self, tmp_path):
        """Test plugin_template handles name that already has correct suffix."""
        output_dir = str(tmp_path / "test_output")
        plugin_template_func(type="fetcher", name="CustomFetcher", output_dir=output_dir)
        
        # Should not double-add suffix
        plugin_file = Path(output_dir) / "customfetcher.py"
        assert plugin_file.exists()
        
        content = plugin_file.read_text()
        assert "class CustomFetcher(BaseFetcher):" in content
        assert "class CustomFetcherFetcher" not in content
    
    def test_plugin_template_default_output_dir(self):
        """Test plugin_template uses default output directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp_dir)
                plugin_template_func(type="fetcher", name="Custom", output_dir="plugin_templates")
                
                # Should create in default 'plugin_templates' directory
                plugin_file = Path("plugin_templates") / "custom.py"
                assert plugin_file.exists()
                
            finally:
                os.chdir(original_cwd)
    
    def test_plugin_template_directory_creation_error(self, tmp_path):
        """Test plugin_template handles directory creation errors."""
        # Try to create directory in non-existent parent
        invalid_path = str(tmp_path / "nonexistent" / "very" / "deep" / "path")
        
        with patch('os.makedirs', side_effect=PermissionError("Permission denied")), \
             patch('typer.echo') as mock_echo:
            
            with pytest.raises(typer.Exit) as exc_info:
                plugin_template_func(type="fetcher", name="Custom", output_dir=invalid_path)
            
            assert exc_info.value.exit_code == 1
            mock_echo.assert_called_with(
                f"[ERROR] Failed to create output directory '{invalid_path}': Permission denied", 
                err=True
            )
    
    def test_plugin_template_file_write_error(self, tmp_path):
        """Test plugin_template handles file write errors."""
        output_dir = str(tmp_path / "test_output")
        
        with patch('builtins.open', side_effect=IOError("Disk full")), \
             patch('typer.echo') as mock_echo:
            
            with pytest.raises(typer.Exit) as exc_info:
                plugin_template_func(type="fetcher", name="Custom", output_dir=output_dir)
            
            assert exc_info.value.exit_code == 1
            mock_echo.assert_any_call("[ERROR] Failed to write template files: Disk full", err=True)


class TestPluginTemplateContent:
    """Test plugin template content generation."""
    
    def test_fetcher_template_content(self, tmp_path):
        """Test fetcher template has correct content structure."""
        output_dir = str(tmp_path / "test_output")
        
        plugin_template_func(type="fetcher", name="MyCustom", output_dir=output_dir)
        
        plugin_file = Path(output_dir) / "mycustom.py"
        content = plugin_file.read_text()
        
        # Check imports
        assert "from ..registry import register" in content
        assert "from ..base_fetcher import BaseFetcher" in content
        assert "from ..models import SubscriptionSource, ParsedServer" in content
        
        # Check class definition
        assert "@register(\"custom_fetcher\")" in content
        assert "class MyCustomFetcher(BaseFetcher):" in content
        
        # Check docstring
        assert "MyCustomFetcher fetches subscription data from custom source." in content
        assert "Example:" in content
        assert "fetcher = MyCustomFetcher(source)" in content
        
        # Check method
        assert "def fetch(self, force_reload: bool = False) -> bytes:" in content
        assert "force_reload: Whether to bypass cache and force fresh data retrieval." in content
        assert "Returns:" in content
        assert "Raw subscription data as bytes." in content
        assert "raise NotImplementedError(\"Implement your custom fetch logic here\")" in content
    
    def test_parser_template_content(self, tmp_path):
        """Test parser template has correct content structure."""
        output_dir = str(tmp_path / "test_output")
        
        plugin_template_func(type="parser", name="MyCustom", output_dir=output_dir)
        
        plugin_file = Path(output_dir) / "mycustom.py"
        content = plugin_file.read_text()
        
        # Check imports
        assert "from ..registry import register" in content
        assert "from ..base_parser import BaseParser" in content
        
        # Check class definition
        assert "@register(\"custom_parser\")" in content
        assert "class MyCustomParser(BaseParser):" in content
        
        # Check method
        assert "def parse(self, raw: bytes) -> list[ParsedServer]:" in content
        assert "raw: Raw subscription data as bytes." in content
        assert "List of ParsedServer objects representing the server configurations." in content
    
    def test_validator_template_content(self, tmp_path):
        """Test validator template has correct content structure."""
        output_dir = str(tmp_path / "test_output")
        
        plugin_template_func(type="validator", name="MyCustom", output_dir=output_dir)
        
        plugin_file = Path(output_dir) / "mycustom.py"
        content = plugin_file.read_text()
        
        # Check imports (no registry for validators)
        assert "from ..validators.base import BaseValidator" in content
        assert "from ..registry import register" not in content
        
        # Check class definition (no decorator)
        assert "@register" not in content
        assert "class MyCustomValidator(BaseValidator):" in content
        
        # Check method
        assert "def validate(self, raw: bytes, context=None):" in content
        assert "ValidationResult indicating whether the data is valid." in content
    
    def test_test_template_content(self, tmp_path):
        """Test generated test file has correct content."""
        output_dir = str(tmp_path / "test_output")
        
        plugin_template_func(type="fetcher", name="MyCustom", output_dir=output_dir)
        
        test_file = Path(output_dir) / "template_test_mycustom.py"
        content = test_file.read_text()
        
        # Check imports
        assert "import pytest" in content
        assert "from sboxmgr.subscription.models import SubscriptionSource, ParsedServer" in content
        assert "from sboxmgr.subscription.fetchers.mycustomfetcher import MyCustomFetcher" in content
        
        # Check test function
        assert "def test_mycustomfetcher_basic():" in content
        assert "plugin = MyCustomFetcher()" in content
        assert "with pytest.raises(NotImplementedError):" in content
        assert "plugin.fetch(None)" in content


class TestPluginTemplateEdgeCases:
    """Test edge cases and special scenarios."""
    
    def test_plugin_template_complex_name(self, tmp_path):
        """Test plugin_template with complex names."""
        output_dir = str(tmp_path / "test_output")
        
        # Test with underscores and numbers
        plugin_template_func(type="fetcher", name="My_Custom_V2", output_dir=output_dir)
        
        plugin_file = Path(output_dir) / "my_custom_v2.py"
        assert plugin_file.exists()
        
        content = plugin_file.read_text()
        assert "class My_Custom_V2Fetcher(BaseFetcher):" in content
    
    def test_plugin_template_all_types_coverage(self, tmp_path):
        """Test all supported plugin types are generated correctly."""
        output_dir = str(tmp_path / "test_output")
        
        types_and_expected = [
            ("fetcher", "BaseFetcher", "def fetch("),
            ("parser", "BaseParser", "def parse("),
            ("validator", "BaseValidator", "def validate(self, raw: bytes, context=None):"),
            ("parsed_validator", "BaseParsedValidator", "def validate(self, servers: list[ParsedServer], context):"),
            ("exporter", "BaseExporter", "def export("),
            ("postprocessor", "BasePostProcessor", "def process("),
        ]
        
        for plugin_type, base_class, method_signature in types_and_expected:
            plugin_template_func(type=plugin_type, name="Test", output_dir=output_dir)
            
            plugin_file = Path(output_dir) / "test.py"
            content = plugin_file.read_text()
            
            assert base_class in content
            assert method_signature in content
            
            # Clean up for next iteration
            plugin_file.unlink()
            (Path(output_dir) / "template_test_test.py").unlink()
    
    def test_plugin_template_debug_output(self, tmp_path):
        """Test debug output messages."""
        output_dir = str(tmp_path / "test_output")
        
        with patch('typer.echo') as mock_echo:
            plugin_template_func(type="fetcher", name="Custom", output_dir=output_dir)
        
        # Check debug messages
        plugin_file = Path(output_dir) / "custom.py"
        test_file = Path(output_dir) / "template_test_custom.py"
        
        mock_echo.assert_any_call(f"[DEBUG] Attempting to write template to {plugin_file}")
        mock_echo.assert_any_call(f"[DEBUG] Successfully wrote {plugin_file}")
        mock_echo.assert_any_call(f"[DEBUG] Successfully wrote {test_file}")
        mock_echo.assert_any_call(f"Created {plugin_file} and {test_file}")
        mock_echo.assert_any_call("[DX] Don't forget to register your plugin in the registry and add tests!")
    
    def test_plugin_template_no_decorator_types(self, tmp_path):
        """Test types that don't use decorators."""
        output_dir = str(tmp_path / "test_output")
        
        with patch('typer.echo') as mock_echo:
            plugin_template_func(type="validator", name="Custom", output_dir=output_dir)
        
        plugin_file = Path(output_dir) / "custom.py"
        content = plugin_file.read_text()
        
        # Validator shouldn't have decorator
        assert "@register" not in content
        
        # Should not show decorator-related message
        dx_calls = [call for call in mock_echo.call_args_list 
                   if "[DX] Don't forget to register" in str(call)]
        assert len(dx_calls) == 0


class TestPluginTemplateIntegration:
    """Integration tests for plugin template generation."""
    
    def test_plugin_template_full_workflow(self, tmp_path):
        """Test complete workflow of generating and validating templates."""
        output_dir = str(tmp_path / "integration_test")
        
        # Generate all types
        plugin_types = ["fetcher", "parser", "validator", "exporter", "postprocessor", "parsed_validator"]
        
        for plugin_type in plugin_types:
            plugin_template_func(type=plugin_type, name=f"Test{plugin_type.title()}", output_dir=output_dir)
        
        # Verify all files were created
        for plugin_type in plugin_types:
            name = f"test{plugin_type.lower()}"
            plugin_file = Path(output_dir) / f"{name}.py"
            test_file = Path(output_dir) / f"template_test_{name}.py"
            
            assert plugin_file.exists(), f"Plugin file missing for {plugin_type}"
            assert test_file.exists(), f"Test file missing for {plugin_type}"
            
            # Verify basic content structure
            content = plugin_file.read_text()
            assert f"class Test{plugin_type.title()}" in content
            assert "raise NotImplementedError(" in content
            
            test_content = test_file.read_text()
            assert "import pytest" in test_content
            assert "NotImplementedError" in test_content
    
    def test_plugin_template_existing_directory(self, tmp_path):
        """Test plugin_template works with existing directory."""
        output_dir = str(tmp_path / "existing")
        os.makedirs(output_dir)
        
        # Should work without error
        plugin_template_func(type="fetcher", name="Custom", output_dir=output_dir)
        
        plugin_file = Path(output_dir) / "custom.py"
        assert plugin_file.exists()
    
    def test_plugin_template_unicode_handling(self, tmp_path):
        """Test plugin_template handles unicode in names and paths."""
        output_dir = str(tmp_path / "unicode_тест")
        
        plugin_template_func(type="fetcher", name="CustomТест", output_dir=output_dir)
        
        plugin_file = Path(output_dir) / "customтест.py"
        assert plugin_file.exists()
        
        content = plugin_file.read_text(encoding='utf-8')
        assert "class CustomТестFetcher(BaseFetcher):" in content 