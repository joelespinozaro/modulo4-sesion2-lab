from src.services.guardrails.layer6_url_filter import UrlFilterMiddleware
from tests.guardrails.conftest import build_state


def test_loads_at_least_60_tlds_and_20_shorteners():
    middleware = UrlFilterMiddleware()
    assert len(middleware._tlds) >= 60
    assert len(middleware._shorteners) >= 20


def test_blocks_url_with_protocol():
    middleware = UrlFilterMiddleware()
    state = build_state("Revisa esto: https://sitio-sospechoso.xyz/login")

    result = middleware.before_agent(state, runtime=None)

    assert result is not None
    assert result["jump_to"] == "end"


def test_blocks_bare_domain_without_protocol():
    middleware = UrlFilterMiddleware()
    state = build_state("Entra a promo-academia.pe y gana un premio")

    result = middleware.before_agent(state, runtime=None)

    assert result is not None


def test_blocks_known_shortener():
    middleware = UrlFilterMiddleware()
    state = build_state("Click aquí: bit.ly/oferta-especial")

    result = middleware.before_agent(state, runtime=None)

    assert result is not None


def test_passes_message_without_urls():
    middleware = UrlFilterMiddleware()
    state = build_state("¿Cuáles son los requisitos de admisión?")

    result = middleware.before_agent(state, runtime=None)

    assert result is None
