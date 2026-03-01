"""Tests for query router with command classification."""

from code_brain.query.router import route_query, QueryType, RoutedQuery


class TestRouteQuery:
    """Test command classification and routing."""

    def test_map_command_with_target(self):
        result = route_query("map src/models/user.py")
        assert result.query_type == QueryType.MAP
        assert result.target == "src/models/user.py"

    def test_map_command_no_target(self):
        result = route_query("map")
        assert result.query_type == QueryType.MAP
        assert result.target is None

    def test_hotspots_command(self):
        result = route_query("hotspots")
        assert result.query_type == QueryType.HOTSPOTS
        assert result.target is None

    def test_hotspots_command_with_target(self):
        result = route_query("hotspots src/services/")
        assert result.query_type == QueryType.HOTSPOTS
        assert result.target == "src/services/"

    def test_arch_command(self):
        result = route_query("arch")
        assert result.query_type == QueryType.ARCH
        assert result.target is None

    def test_architecture_full_word(self):
        result = route_query("architecture src/")
        assert result.query_type == QueryType.ARCH
        assert result.target == "src/"

    def test_explain_command(self):
        result = route_query("explain AuthService.authenticate")
        assert result.query_type == QueryType.EXPLAIN
        assert result.target == "AuthService.authenticate"

    def test_search_command(self):
        result = route_query("search UserRepository")
        assert result.query_type == QueryType.SEARCH
        assert result.target == "UserRepository"

    def test_natural_language_routes_to_semantic(self):
        result = route_query("how does authentication work?")
        assert result.query_type == QueryType.SEMANTIC

    def test_another_natural_language_query(self):
        result = route_query("what classes inherit from User?")
        assert result.query_type == QueryType.SEMANTIC

    def test_case_insensitive_command(self):
        result = route_query("MAP src/models")
        assert result.query_type == QueryType.MAP
        assert result.target == "src/models"

    def test_mixed_case_command(self):
        result = route_query("Explain something")
        assert result.query_type == QueryType.EXPLAIN
        assert result.target == "something"

    def test_preserves_raw_query(self):
        raw = "  explain something  "
        result = route_query(raw)
        assert result.raw_query == raw

    def test_strips_whitespace_for_matching(self):
        result = route_query("  hotspots  ")
        assert result.query_type == QueryType.HOTSPOTS

    def test_routed_query_dataclass(self):
        rq = RoutedQuery(
            query_type=QueryType.MAP,
            raw_query="map foo",
            target="foo",
        )
        assert rq.query_type == QueryType.MAP
        assert rq.raw_query == "map foo"
        assert rq.target == "foo"

    def test_routed_query_default_target_is_none(self):
        rq = RoutedQuery(query_type=QueryType.SEMANTIC, raw_query="hello")
        assert rq.target is None

    def test_empty_query_routes_to_semantic(self):
        result = route_query("")
        assert result.query_type == QueryType.SEMANTIC

    def test_command_prefix_not_in_middle(self):
        """A command word in the middle of a sentence should not trigger routing."""
        result = route_query("please explain the map function")
        assert result.query_type == QueryType.SEMANTIC
