def test_core_modules_importable():
    import feed_adapters
    import feed_provider
    import normalizer
    import providers

    assert feed_adapters is not None
    assert feed_provider is not None
    assert normalizer is not None
    assert providers is not None
