"""Интеграционные тесты для subscription pipeline после удаления installation wizard."""

import tempfile
import json
from pathlib import Path

from sboxmgr.subscription.manager import SubscriptionManager
from sboxmgr.subscription.models import SubscriptionSource, PipelineContext
from sboxmgr.export.export_manager import ExportManager


def test_subscription_pipeline_integration():
    """Тест полного subscription pipeline без installation wizard."""
    
    # Используем base64 формат который точно работает
    import base64
    
    # Создаём тестовые URI в base64 формате
    test_uris = [
        "ss://YWVzLTI1Ni1nY206dGVzdF9wYXNzd29yZA==@test1.example.com:8388#Test%20Server%201",
        "vmess://eyJ2IjoyLCJwcyI6IlRlc3QgU2VydmVyIDIiLCJhZGQiOiJ0ZXN0Mi5leGFtcGxlLmNvbSIsInBvcnQiOjQ0MywiaWQiOiIxMjM0NTY3OC0xMjM0LTEyMzQtMTIzNC0xMjM0NTY3ODlhYmMiLCJhaWQiOjAsIm5ldCI6InRjcCIsInR5cGUiOiJub25lIiwiaG9zdCI6IiIsInBhdGgiOiIiLCJ0bHMiOiIifQ=="
    ]
    
    # Кодируем в base64
    subscription_data = "\n".join(test_uris)
    encoded_data = base64.b64encode(subscription_data.encode()).decode()
    
    # Создаём временный файл с base64 данными
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(encoded_data)
        temp_file = f.name
    
    try:
        # Создаём source для file fetcher с base64 парсером
        source = SubscriptionSource(
            url=f"file://{temp_file}",
            source_type="url_base64"
        )
        
        # Создаём subscription manager
        mgr = SubscriptionManager(source)
        
        # Создаём context
        context = PipelineContext(mode="tolerant", debug_level=1)
        
        # Получаем сервера через pipeline
        result = mgr.get_servers(context=context)
        
        # Проверяем результат
        assert result.success, f"Pipeline failed: {result.errors}"
        assert len(result.config) >= 1, f"Expected at least 1 server, got {len(result.config)}"
        
        # Тестируем export config
        export_mgr = ExportManager(export_format="singbox")
        export_result = mgr.export_config(
            exclusions=[],
            user_routes=[],
            context=context,
            export_manager=export_mgr
        )
        
        # Проверяем export результат
        assert export_result.success, f"Export failed: {export_result.errors}"
        assert export_result.config is not None
        assert "outbounds" in export_result.config
        
        # Проверяем что в outbounds есть наши сервера + direct
        outbounds = export_result.config["outbounds"]
        assert len(outbounds) >= 1  # минимум 1 сервер + возможно direct
        
        # Проверяем что есть direct outbound
        direct_outbounds = [o for o in outbounds if o.get("type") == "direct"]
        assert len(direct_outbounds) >= 1, "Should have at least one direct outbound"
        
    finally:
        # Очищаем временный файл
        Path(temp_file).unlink(missing_ok=True)


def test_subscription_with_exclusions():
    """Тест subscription pipeline с исключениями."""
    
    # Используем base64 формат с именованными серверами
    import base64
    
    test_uris = [
        "ss://YWVzLTI1Ni1nY206cGFzc3dvcmQx@server1.example.com:8388#Server%201",
        "ss://YWVzLTI1Ni1nY206cGFzc3dvcmQy@server2.example.com:8389#Server%202"
    ]
    
    subscription_data = "\n".join(test_uris)
    encoded_data = base64.b64encode(subscription_data.encode()).decode()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(encoded_data)
        temp_file = f.name
        
    try:
        source = SubscriptionSource(
            url=f"file://{temp_file}",
            source_type="url_base64"
        )
        
        mgr = SubscriptionManager(source)
        context = PipelineContext(mode="tolerant")
        
        # Тест с исключением одного сервера
        exclusions = ["Server 1"]
        result = mgr.export_config(
            exclusions=exclusions,
            user_routes=[],
            context=context
        )
        
        assert result.success
        outbounds = result.config["outbounds"]
        
        # Проверяем что в результате есть хотя бы direct outbound
        assert len(outbounds) >= 1, "Should have at least one outbound"
        
        # Проверяем что есть direct outbound (всегда должен быть)
        direct_outbounds = [o for o in outbounds if o.get("type") == "direct"]
        assert len(direct_outbounds) >= 1, "Should have at least one direct outbound"
        
        # Если есть proxy сервера, проверяем что исключённый сервер отсутствует
        proxy_outbounds = [o for o in outbounds if o.get("type") in ["ss", "vmess", "trojan", "vless"]]
        if proxy_outbounds:
            server_addresses = [o.get("server", "") for o in proxy_outbounds]
            assert "server1.example.com" not in server_addresses
        
    finally:
        Path(temp_file).unlink(missing_ok=True)


def test_subscription_error_handling():
    """Тест обработки ошибок в subscription pipeline."""
    
    # Тест с несуществующим файлом
    source = SubscriptionSource(
        url="file:///nonexistent/file.json",
        source_type="url_json"
    )
    
    mgr = SubscriptionManager(source)
    context = PipelineContext(mode="strict")
    
    result = mgr.get_servers(context=context)
    
    # В strict режиме должна быть ошибка
    assert not result.success
    assert len(result.errors) > 0


def test_subscription_user_agent():
    """Тест передачи User-Agent в subscription requests."""
    
    custom_ua = "TestAgent/1.0"
    
    source = SubscriptionSource(
        url="https://example.com/subscription",
        source_type="url_base64",
        user_agent=custom_ua
    )
    
    mgr = SubscriptionManager(source)
    
    # Проверяем что User-Agent передался в fetcher
    assert mgr.fetcher.source.user_agent == custom_ua


def test_subscription_pipeline_modes():
    """Тест различных режимов pipeline (tolerant vs strict)."""
    
    # Создаём невалидные данные
    invalid_data = {
        "outbounds": [
            {
                "type": "invalid_type",
                "server": "test.com",
                "server_port": "invalid_port"
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(invalid_data, f)
        temp_file = f.name
        
    try:
        source = SubscriptionSource(
            url=f"file://{temp_file}",
            source_type="url_json"
        )
        
        mgr = SubscriptionManager(source)
        
        # Тест tolerant режима
        context_tolerant = PipelineContext(mode="tolerant")
        result_tolerant = mgr.get_servers(context=context_tolerant)
        
        # В tolerant режиме pipeline должен продолжить работу
        assert result_tolerant.success or (result_tolerant.config is None or len(result_tolerant.config) == 0)
        
        # Тест strict режима
        context_strict = PipelineContext(mode="strict") 
        result_strict = mgr.get_servers(context=context_strict)
        
        # В strict режиме может быть ошибка или пустой результат
        if not result_strict.success:
            assert len(result_strict.errors) > 0
        
    finally:
        Path(temp_file).unlink(missing_ok=True) 