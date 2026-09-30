"""Request parsers. Every JSON endpoint here expects an object; anything else is a 400."""

from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser


class ObjectJSONParser(JSONParser):
    """JSON body must be an object, so views can safely call `request.data.get(...)`."""

    def parse(self, stream, media_type=None, parser_context=None):
        data = super().parse(stream, media_type, parser_context)
        if not isinstance(data, dict):
            raise ParseError("Send a JSON object.")
        return data
