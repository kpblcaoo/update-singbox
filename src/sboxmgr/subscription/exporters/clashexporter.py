"""Clash configuration exporter implementation.

This module provides the ClashExporter class for converting parsed server
configurations into Clash-compatible YAML format. It handles Clash-specific
configuration structure, proxy groups, and routing rules for seamless
integration with Clash clients.
"""
from ..base_exporter import BaseExporter
class ClashExporter(BaseExporter):
    """ClashExporter exports parsed servers to config.

Example:
    exporter = ClashExporter()
    config = exporter.export(servers)"""
    def export(self, servers):
        """Export parsed servers to config.

        Args:
            servers (list[ParsedServer]): List of servers.

        Returns:
            dict: Exported config.
        """
        raise NotImplementedError()

