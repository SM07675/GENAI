"""Utilities Toolkit: Weather, Time, Math, and Clipboard."""

import datetime
import requests
from ..schemas import ToolResult
from .registry import tool

@tool
def get_weather(location: str) -> ToolResult:
    """Get the current live weather for a specific city or location.
    
    :param location: The city name (e.g. 'London', 'New York', 'Mumbai').
    """
    try:
        # Step 1: Geocode the location
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1&language=en&format=json"
        geo_res = requests.get(geo_url, timeout=10).json()
        
        if not geo_res.get("results"):
            return ToolResult(status="not_found", message=f"Could not find coordinates for {location}.")
            
        loc_data = geo_res["results"][0]
        lat, lon = loc_data["latitude"], loc_data["longitude"]
        name = loc_data.get("name", location)
        
        # Step 2: Get weather
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        weather_res = requests.get(weather_url, timeout=10).json()
        
        cw = weather_res.get("current_weather", {})
        temp = cw.get("temperature", "unknown")
        wind = cw.get("windspeed", "unknown")
        
        # Open-Meteo WMO weather codes (simplified)
        code = cw.get("weathercode", 0)
        desc = "Clear" if code <= 1 else "Cloudy" if code <= 3 else "Rain/Showers" if code <= 65 else "Snow/Storm"
        
        msg = f"The current weather in {name} is {temp}°C, {desc}, with wind speeds around {wind} km/h."
        return ToolResult(status="ok", message=msg, data={"location": name, "temperature_c": temp, "condition": desc})
        
    except Exception as e:
        return ToolResult(status="error", message=f"Failed to fetch weather: {e}")

@tool
def get_time(timezone_name: str = "local") -> ToolResult:
    """Get the current precise time and date.
    
    :param timezone_name: Optional timezone name (e.g., 'local', 'UTC', 'America/New_York').
    """
    try:
        if timezone_name.lower() == "local":
            now = datetime.datetime.now()
        elif timezone_name.upper() == "UTC":
            now = datetime.datetime.utcnow()
        else:
            # Simple fallback for unknown timezones (could use pytz or zoneinfo in a fuller implementation)
            now = datetime.datetime.now()
            
        formatted = now.strftime("%A, %B %d, %Y at %I:%M %p")
        return ToolResult(status="ok", message=f"The current time is {formatted}.", data={"time": formatted})
    except Exception as e:
        return ToolResult(status="error", message=str(e))

@tool
def calculate(expression: str) -> ToolResult:
    """Evaluate a mathematical expression.
    
    :param expression: The math expression (e.g., '25 * 420 / 3.14').
    """
    import ast
    import math
    import operator

    allowed_binary_ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    allowed_unary_ops = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }
    allowed_names = {
        "pi": math.pi,
        "e": math.e,
        "tau": math.tau,
    }
    allowed_functions = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "ceil": math.ceil,
        "floor": math.floor,
    }

    def eval_node(node):
        if isinstance(node, ast.Expression):
            return eval_node(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name) and node.id in allowed_names:
            return allowed_names[node.id]
        if isinstance(node, ast.UnaryOp) and type(node.op) in allowed_unary_ops:
            return allowed_unary_ops[type(node.op)](eval_node(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in allowed_binary_ops:
            left = eval_node(node.left)
            right = eval_node(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("Exponent is too large.")
            return allowed_binary_ops[type(node.op)](left, right)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            func = allowed_functions.get(node.func.id)
            if func is None:
                raise ValueError(f"Function '{node.func.id}' is not allowed.")
            if node.keywords:
                raise ValueError("Keyword arguments are not supported.")
            return func(*(eval_node(arg) for arg in node.args))
        raise ValueError("Only numbers, basic operators, and safe math functions are allowed.")

    try:
        tree = ast.parse(expression, mode="eval")
        result = eval_node(tree)
        return ToolResult(status="ok", message=f"The result is {result}.", data={"result": result, "expression": expression})
    except Exception as e:
        return ToolResult(status="error", message=f"Invalid math expression: {e}")

@tool
def clipboard_read() -> ToolResult:
    """Read the current text from the system clipboard."""
    try:
        import pyperclip
        text = pyperclip.paste()
        if not text:
            return ToolResult(status="not_found", message="The clipboard is empty.")
        return ToolResult(status="ok", message="Read from clipboard.", data={"text": text})
    except ImportError:
        return ToolResult(status="error", message="pyperclip is not installed.")
    except Exception as e:
        return ToolResult(status="error", message=str(e))

@tool
def clipboard_write(text: str) -> ToolResult:
    """Write text to the system clipboard.
    
    :param text: The text to copy to the clipboard.
    """
    try:
        import pyperclip
        pyperclip.copy(text)
        return ToolResult(status="ok", message="Successfully copied to clipboard.")
    except Exception as e:
        return ToolResult(status="error", message=str(e))
