class Color:
    def __init__(self, color: int = None, failed: bool = False):
        self.color: int = color
        self.failed: bool = failed

    @staticmethod
    def decode(color: str) -> 'Color':
        try:
            color_hex = int(color, 16)

        except:
            return Color(failed=True)

        else:
            if 0 <= color_hex <= 0xFFFFFF:
                return Color(color=color_hex)

            else:
                return Color(failed=True)
