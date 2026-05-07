import logging

from github_scrape.logging_cfg import get_logger, setup_logging


class TestSetupLogging:
    def test_setup_sets_level(self) -> None:
        setup_logging(logging.DEBUG)
        root = logging.getLogger("github_scrape")
        assert root.level == logging.DEBUG

    def test_setup_clears_old_handlers(self) -> None:
        setup_logging(logging.WARNING)
        root = logging.getLogger("github_scrape")
        assert len(root.handlers) == 1


class TestGetLogger:
    def test_get_logger_returns_child(self) -> None:
        logger = get_logger("test")
        assert logger.name == "github_scrape.test"

    def test_get_logger_inherits_level(self) -> None:
        setup_logging(logging.INFO)
        logger = get_logger("api")
        assert logger.getEffectiveLevel() == logging.INFO
