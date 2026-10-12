"""Tests for svg_map_generator module."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from custom_components.dreame_mower.dreame.map_data_parser import (
    parse_batch_map_data,
    vector_map_to_map_data,
)
from custom_components.dreame_mower.dreame.svg_map_generator import (
    calculate_bounds,
    coord_to_pixel,
    create_svg_document,
    svg_path_from_segments,
    svg_polygon,
    svg_circle,
    svg_dashed_path,
    svg_text_with_background,
    finish_svg_document,
    generate_svg_map_image,
    fit_canvas,
)


# Path to test data
TEST_DATA_DIR = Path(__file__).parent / "test_data"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
GOLDEN_JSON_FILE = TEST_DATA_DIR / "test_svg_map_generator.json"


@pytest.fixture
def golden_map_data():
    """Load the golden JSON test data."""
    with open(GOLDEN_JSON_FILE, 'r') as f:
        return json.load(f)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator for map generation tests."""
    coordinator = Mock()
    coordinator.device = Mock()
    coordinator.device.mower_coordinates = None
    return coordinator


class TestCalculateBounds:
    """Test suite for calculate_bounds function."""

    @pytest.mark.parametrize(
        "points,expected",
        [
            # Empty list returns default bounds
            ([], (0, 0, 100, 100)),
            
            # Only sentinel values returns default bounds
            ([[2147483647, 2147483647], [2147483647, 2147483647]], (0, 0, 100, 100)),
            
            # Normal rectangular bounds
            ([[0, 0], [1000, 0], [1000, 800], [0, 800]], (0, 0, 1000, 800)),
            
            # Mixed valid and sentinel values (filters out sentinels)
            ([[100, 200], [2147483647, 2147483647], [300, 400], [500, 600]], (100, 200, 500, 600)),
            
            # Negative coordinates
            ([[-100, -200], [100, 200], [0, 0]], (-100, -200, 100, 200)),
        ],
    )
    def test_calculate_bounds(self, points, expected):
        """Test calculate_bounds with various input scenarios."""
        result = calculate_bounds(points)
        assert result == expected


class TestCoordToPixel:
    """Test suite for coord_to_pixel function."""

    @pytest.mark.parametrize(
        "x,y,bounds,img_width,img_height,padding,expected",
        [
            # Bottom-left corner (Y coordinate is flipped in SVG; map is centred vertically)
            (0, 0, (0, 0, 1000, 800), 1200, 1000, 50, (50, 940)),
            
            # Top-right corner
            (1000, 800, (0, 0, 1000, 800), 1200, 1000, 50, (1150, 59)),
            
            # Center point (aspect ratio preserved, map centred)
            (500, 400, (0, 0, 1000, 800), 1200, 1000, 50, (600, 500)),
            
            # Single point bounds - function adds 100 to create valid dimensions; map centred horizontally
            (100, 200, (100, 200, 100, 200), 1200, 1000, 50, (150, 950)),
            
            # Negative coordinates with aspect ratio maintained; map centred horizontally
            (0, 0, (-100, -200, 100, 200), 1200, 1000, 50, (600, 500)),
        ],
    )
    def test_coord_to_pixel(self, x, y, bounds, img_width, img_height, padding, expected):
        """Test coord_to_pixel with various input scenarios."""
        result = coord_to_pixel(x, y, bounds, img_width, img_height, padding)
        assert result == expected


class TestCreateSvgDocument:
    """Test suite for create_svg_document function."""

    @pytest.mark.parametrize(
        "width,height,background_color,expected_lines",
        [
            # Default white background
            (1200, 1000, "white", 3),
            
            # Custom color
            (800, 600, "#add8e6", 3),
            
            # Small dimensions
            (100, 100, "#ffffff", 3),
        ],
    )
    def test_create_svg_document(self, width, height, background_color, expected_lines):
        """Test create_svg_document with various parameters."""
        result = create_svg_document(width, height, background_color)
        assert len(result) == expected_lines
        assert result[0] == '<?xml version="1.0" encoding="UTF-8"?>'
        assert f'width="{width}"' in result[1]
        assert f'height="{height}"' in result[1]
        assert f'fill="{background_color}"' in result[2]


class TestSvgPathFromSegments:
    """Test suite for svg_path_from_segments function."""

    @pytest.mark.parametrize(
        "segments,bounds,img_width,img_height,stroke_color,stroke_width,expected_result",
        [
            # Empty segments returns empty string
            ([], (0, 0, 1000, 800), 1200, 1000, "#ff0000", 2, ""),
            
            # Single segment with two points
            ([[[0, 0], [100, 100]]], (0, 0, 1000, 800), 1200, 1000, "#ff0000", 2, "valid_path"),
            
            # Multiple segments
            ([[[0, 0], [100, 100]], [[200, 200], [300, 300]]], (0, 0, 1000, 800), 1200, 1000, "#00ff00", 3, "valid_path"),
            
            # Segment with single point (too short, skipped but still returns path element with empty data)
            ([[[100, 100]]], (0, 0, 1000, 800), 1200, 1000, "#0000ff", 2, "empty_path"),
        ],
    )
    def test_svg_path_from_segments(self, segments, bounds, img_width, img_height, stroke_color, stroke_width, expected_result):
        """Test svg_path_from_segments with various inputs."""
        result = svg_path_from_segments(segments, bounds, img_width, img_height, stroke_color, stroke_width)
        if expected_result == "":
            assert result == ""
        elif expected_result == "valid_path":
            assert "M " in result and "L " in result
            assert f'stroke="{stroke_color}"' in result
            assert f'stroke-width="{stroke_width}"' in result
        elif expected_result == "empty_path":
            assert '<path d=""' in result
            assert f'stroke="{stroke_color}"' in result


class TestSvgPolygon:
    """Test suite for svg_polygon function."""

    @pytest.mark.parametrize(
        "points,bounds,img_width,img_height,fill_color,stroke_color,expected_tag",
        [
            # Valid triangle
            ([[0, 0], [100, 0], [50, 100]], (0, 0, 1000, 800), 1200, 1000, "#ff0000", "#000000", "polygon"),
            
            # Valid rectangle
            ([[0, 0], [100, 0], [100, 100], [0, 100]], (0, 0, 1000, 800), 1200, 1000, "#00ff00", "#000000", "polygon"),
            
            # Too few points (less than 3) returns empty
            ([[0, 0], [100, 100]], (0, 0, 1000, 800), 1200, 1000, "#0000ff", "#000000", None),
        ],
    )
    def test_svg_polygon(self, points, bounds, img_width, img_height, fill_color, stroke_color, expected_tag):
        """Test svg_polygon with various inputs."""
        result = svg_polygon(points, bounds, img_width, img_height, fill_color, stroke_color)
        if expected_tag is None:
            assert result == ""
        else:
            assert f'<{expected_tag}' in result
            assert f'fill="{fill_color}"' in result
            assert f'stroke="{stroke_color}"' in result


class TestSvgCircle:
    """Test suite for svg_circle function."""

    @pytest.mark.parametrize(
        "x,y,bounds,img_width,img_height,radius,fill_color,stroke_color",
        [
            # Center position
            (500, 400, (0, 0, 1000, 800), 1200, 1000, 10, "#ff0000", "#000000"),
            
            # Corner position
            (0, 0, (0, 0, 1000, 800), 1200, 1000, 5, "#00ff00", "#ffffff"),
            
            # Large radius
            (250, 250, (0, 0, 500, 500), 800, 600, 50, "#0000ff", "#ffff00"),
        ],
    )
    def test_svg_circle(self, x, y, bounds, img_width, img_height, radius, fill_color, stroke_color):
        """Test svg_circle with various inputs."""
        result = svg_circle(x, y, bounds, img_width, img_height, radius, fill_color, stroke_color)
        assert '<circle' in result
        assert f'r="{radius}"' in result
        assert f'fill="{fill_color}"' in result
        assert f'stroke="{stroke_color}"' in result


class TestSvgDashedPath:
    """Test suite for svg_dashed_path function."""

    @pytest.mark.parametrize(
        "points,bounds,img_width,img_height,stroke_color,stroke_width,expected_contains",
        [
            # Valid path with multiple points
            ([[0, 0], [100, 100], [200, 200]], (0, 0, 1000, 800), 1200, 1000, "#ff0000", 3, ["M ", "L ", 'stroke-dasharray="10,5"', 'stroke="#ff0000"']),
            
            # Two points (minimum)
            ([[0, 0], [500, 500]], (0, 0, 1000, 800), 1200, 1000, "#00ff00", 2, ["M ", "L ", 'stroke-dasharray="10,5"']),
            
            # Single point (too short) returns empty
            ([[100, 100]], (0, 0, 1000, 800), 1200, 1000, "#0000ff", 2, None),
        ],
    )
    def test_svg_dashed_path(self, points, bounds, img_width, img_height, stroke_color, stroke_width, expected_contains):
        """Test svg_dashed_path with various inputs."""
        result = svg_dashed_path(points, bounds, img_width, img_height, stroke_color, stroke_width)
        if expected_contains is None:
            assert result == ""
        else:
            for expected_str in expected_contains:
                assert expected_str in result


class TestSvgTextWithBackground:
    """Test suite for svg_text_with_background function."""

    @pytest.mark.parametrize(
        "text,x,y,font_size,text_color,bg_color,expected_elements",
        [
            # Single line text
            ("Hello", 10, 20, 12, "#000000", "#ffffff", ["<g>", "<rect", "<text"]),
            
            # Multi-line text
            ("Line 1\nLine 2\nLine 3", 50, 100, 14, "#ff0000", "#ffff00", ["<g>", "<rect", "<text", "Line 1", "Line 2", "Line 3"]),
            
            # Large font
            ("Big Text", 100, 200, 24, "#0000ff", "#00ff00", ["<g>", "<rect", "<text", "Big Text"]),
        ],
    )
    def test_svg_text_with_background(self, text, x, y, font_size, text_color, bg_color, expected_elements):
        """Test svg_text_with_background with various inputs."""
        result = svg_text_with_background(text, x, y, font_size, text_color, bg_color)
        for element in expected_elements:
            assert element in result
        assert f'fill="{bg_color}"' in result
        assert f'fill="{text_color}"' in result


class TestFinishSvgDocument:
    """Test suite for finish_svg_document function."""

    @pytest.mark.parametrize(
        "svg_lines,expected_ending",
        [
            # Simple document
            (["<svg>", "<rect/>"], "</svg>"),
            
            # Empty document
            ([], "</svg>"),
            
            # Document with multiple elements
            (["<svg>", "<circle/>", "<path/>", "<text/>"], "</svg>"),
        ],
    )
    def test_finish_svg_document(self, svg_lines, expected_ending):
        """Test finish_svg_document with various inputs."""
        result = finish_svg_document(svg_lines)
        assert result.endswith(expected_ending)
        assert "\n" in result or len(svg_lines) <= 1  # Contains newlines or is very short


class TestMapBoundaryMultiZone:
    """Test suite for generating SVG from multi-zone map boundary data."""

    def test_generate_svg_map_boundary_zone_separation(self, mock_coordinator):
        """Test generating SVG with proper zone separation in map boundaries.
        
        This test verifies that map boundaries with multiple disconnected zones
        are rendered with proper move operations (M) between zones, rather than
        continuous line operations (L) that would draw connecting lines.
        
        Addresses issue where boundaries were drawn as continuous paths across
        disconnected zones instead of separate zone outlines.
        """
        # Load multi-zone map boundary test data
        map_data_file = TEST_DATA_DIR / "map_boundary_multi_zone.json"
        with open(map_data_file, 'r') as f:
            map_data = json.load(f)
        
        # Generate SVG with no rotation
        result = generate_svg_map_image(map_data, None, mock_coordinator, rotation=0)
        
        # Save output for visual inspection
        output_svg_file = TEST_DATA_DIR / "map_boundary_multi_zone_actual.svg"
        with open(output_svg_file, 'wb') as f:
            f.write(result)
        
        # Load golden file for comparison
        golden_svg_file = TEST_DATA_DIR / "map_boundary_multi_zone_golden.svg"
        with open(golden_svg_file, 'rb') as f:
            expected_result = f.read()
        
        # Compare actual output with golden file
        assert result == expected_result, (
            f"Generated SVG does not match golden file. "
            f"Actual output saved to {output_svg_file}. "
            f"If the changes are intentional, update the golden file."
        )


class TestForbiddenAreaShapes:
    """Golden-image test for the advanced forbidden-area shapes.

    Renders a real device's map (issue #139) that contains circular
    forbidden zones (shapeType 3, stored as a bounding box) and rotated
    rectangular zones (shapeType 2, stored axis-aligned with a separate
    ``angle``). Both must be expanded into renderable polygons; before the fix
    circles drew nothing and rotated rectangles were rendered axis-aligned.
    """

    def test_render_circles_and_tilted_rectangles(self, mock_coordinator):
        batch = json.loads((FIXTURES_DIR / "batch_map_circles_tilted_rect.json").read_text())

        vector_map = parse_batch_map_data(batch)
        assert vector_map is not None
        map_data = vector_map_to_map_data(vector_map)
        # ``start`` is derived from wall-clock time; pin it so the golden SVG
        # (which renders a "Started:" timestamp) is reproducible.
        map_data["start"] = 1747772886  # fixed epoch -> 2025-05-20 20:28:06 UTC

        result = generate_svg_map_image(map_data, None, mock_coordinator, rotation=0)

        actual_svg_file = TEST_DATA_DIR / "batch_map_circles_tilted_rect_actual.svg"
        actual_svg_file.write_bytes(result)

        golden_svg_file = TEST_DATA_DIR / "batch_map_circles_tilted_rect_golden.svg"
        expected_result = golden_svg_file.read_bytes()

        assert result == expected_result, (
            f"Generated SVG does not match golden file. "
            f"Actual output saved to {actual_svg_file}. "
            f"If the changes are intentional, update the golden file."
        )


class TestMapRotation:
    """Test suite for map rotation functionality."""

    def test_generate_rotated_svg_90_degrees(self, golden_map_data, mock_coordinator):
        """Test generating a 90-degree rotated map.
        
        This test verifies that the rotation feature works correctly by generating
        a rotated SVG and comparing against the golden reference file.
        """
        # Generate SVG with 90-degree rotation
        result = generate_svg_map_image(golden_map_data, None, mock_coordinator, rotation=90)
        
        # Save to rotated output file for visual inspection
        rotated_svg_file = TEST_DATA_DIR / "test_svg_map_generator_rotated_90_actual.svg"
        with open(rotated_svg_file, 'wb') as f:
            f.write(result)
        
        # Load golden file for comparison
        golden_svg_file = TEST_DATA_DIR / "test_svg_map_generator_rotated_90_golden.svg"
        with open(golden_svg_file, 'rb') as f:
            expected_result = f.read()
        
        # Compare actual output with golden file
        assert result == expected_result, (
            f"Generated SVG does not match golden file. "
            f"Actual output saved to {rotated_svg_file}. "
            f"If the changes are intentional, update the golden file."
        )

    def test_generate_rotated_svg_180_degrees(self, golden_map_data, mock_coordinator):
        """Test generating a 180-degree rotated map."""
        result = generate_svg_map_image(golden_map_data, None, mock_coordinator, rotation=180)
        
        svg_output = result.decode('utf-8')
        assert 'transform="rotate(180, 600, 600)"' in svg_output
        assert '<g transform="rotate(180, 600, 600)">' in svg_output

    def test_generate_rotated_svg_270_degrees(self, golden_map_data, mock_coordinator):
        """Test generating a 270-degree rotated map."""
        result = generate_svg_map_image(golden_map_data, None, mock_coordinator, rotation=270)
        
        svg_output = result.decode('utf-8')
        assert 'transform="rotate(270, 600, 600)"' in svg_output
        assert '<g transform="rotate(270, 600, 600)">' in svg_output

    def test_generate_unrotated_svg(self, golden_map_data, mock_coordinator):
        """Test generating a map with no rotation (0 degrees).
        
        This test verifies that maps with no rotation are generated correctly
        by comparing against the golden reference file.
        """
        result = generate_svg_map_image(golden_map_data, None, mock_coordinator, rotation=0)
        
        # Save to output file for visual inspection
        output_svg_file = TEST_DATA_DIR / "test_svg_map_generator_rotated_0_actual.svg"
        with open(output_svg_file, 'wb') as f:
            f.write(result)
        
        # Load golden file for comparison
        golden_svg_file = TEST_DATA_DIR / "test_svg_map_generator_rotated_0_golden.svg"
        with open(golden_svg_file, 'rb') as f:
            expected_result = f.read()
        
        # Compare actual output with golden file
        assert result == expected_result, (
            f"Generated SVG does not match golden file. "
            f"Actual output saved to {output_svg_file}. "
            f"If the changes are intentional, update the golden file."
        )


class TestFitCanvas:
    """The canvas can take on the map's proportions instead of a square."""

    def test_a_wide_map_gets_a_wide_canvas(self):
        """A map three times wider than tall keeps the full width, a third of the height."""
        width, height = fit_canvas((0, 0, 90000, 30000), padding=10)
        assert width == 1200
        assert height == round(1180 / 3) + 20 + 30

    def test_a_tall_map_gets_a_tall_canvas(self):
        """A map taller than wide keeps the full height."""
        width, height = fit_canvas((0, 0, 30000, 60000), padding=10)
        assert height == 1200
        assert width == round((1200 - 20 - 30) / 2) + 20

    def test_a_long_narrow_map_keeps_a_readable_canvas(self):
        """The short side never shrinks below the minimum."""
        assert fit_canvas((0, 0, 100000, 1000), padding=10)[1] == 300

    def test_the_generated_image_takes_the_fitted_size(self, mock_coordinator):
        """With fit, the SVG document is sized to the map, not square."""
        mock_coordinator.device.mower_coordinates = None
        data = {"map": [{"data": [[0, 0], [90000, 0], [90000, 30000], [0, 30000], [0, 0]], "track": []}]}

        svg = generate_svg_map_image(data, None, mock_coordinator, rotation=0, padding=10, fit=True).decode()

        assert '<svg width="1200" height="443" viewBox="0 0 1200 443"' in svg


def test_each_mission_of_a_mowing_gets_its_own_colour(mock_coordinator):
    """The latest mission keeps the mowing path colour, an earlier one another."""
    outline = [[0, 0], [9000, 0], [9000, 3000], [0, 3000], [0, 0]]
    data = {
        "map": [{"data": outline, "track": []}],
        "session_tracks": [[[100, 100], [200, 100]], [[300, 300], [400, 300]]],
    }

    svg = generate_svg_map_image(data, None, mock_coordinator, rotation=0).decode()

    assert 'stroke="#8e44ad"' in svg  # the earlier mission
    assert 'stroke="#ffa500"' in svg  # the latest mission


def test_the_legend_dates_each_mission_of_a_mowing(mock_coordinator):
    """With the legend on, each mission's trail is listed by its start (UTC)."""
    outline = [[0, 0], [9000, 0], [9000, 3000], [0, 3000], [0, 0]]
    data = {
        "map": [{"data": outline, "track": []}],
        "session_tracks": [[[100, 100], [200, 100]], [[300, 300], [400, 300]]],
        "session_starts": [1791714776, 1791800014],
        "start": 1791714776,
    }

    svg = generate_svg_map_image(data, None, mock_coordinator, rotation=0, show_legend=True).decode()

    assert "Mowing 2026-10-11 10:32" in svg
    assert "Mowing 2026-10-12 10:13" in svg
