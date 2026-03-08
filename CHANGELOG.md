# Changelog

All notable changes to wisp-ai are documented here.
This project follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [0.1.0] — 2026-03-08

### Added
- `WispDevice` base class with metaclass-powered capability registry
- `@capability` decorator — bare and with arguments
- Multi-provider AI client: Groq, OpenRouter (zero extra dependencies)
- Grounded system prompt builder — AI only calls real capabilities
- Telegram transport (long-polling, no external libs)
- CLI transport for local testing without Telegram
- HTTP webhook transport (stdlib `http.server`)
- Hardware Abstraction Layer (HAL) — MicroPython / smbus2 / mock
- I2C auto-discovery scanner
- Sensor drivers: BME280, BH1750, SHT31, MPU6050, SSD1306
- `WispPlugin` base class + `device.use(plugin)` API
- ROS2 plugin — scans live graph, registers movement / navigation / sensor capabilities
- `wisp` CLI: `new`, `run`, `simulate`, `check`, `version`
- Project templates: basic, sensors, ros2
- Full test suite (pytest)
- `WispConfig` — JSON config + env var loading with validation

[Unreleased]: https://github.com/shaik-shahansha/wisp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/shaik-shahansha/wisp/releases/tag/v0.1.0
