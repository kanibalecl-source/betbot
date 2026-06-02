"""Production module namespace for KANIBAL / BetBot.

The root-level files remain as compatibility entrypoints in Etap 3.
New code should live inside this package so each responsibility can be changed independently.
"""
__all__ = [
    "config", "core", "providers", "prematch", "live", "settlement", "storage",
    "learning", "manual", "gpt", "dashboard", "runtime",
]
