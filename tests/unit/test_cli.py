from job_market_analyzer.cli import main


def test_cli_entry_point_is_callable_without_side_effects(capsys) -> None:
    main()

    captured = capsys.readouterr()
    assert captured.out == "Job Market Analyzer CLI is not implemented yet.\n"
    assert captured.err == ""
