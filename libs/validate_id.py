def validate_id(id_str):
    if not id_str or id_str[0].isdigit() or id_str[0] == "_":
        return False
    allowed_chars = set("abcdefghijklmnopqrstuvwxyz0123456789_")
    return all(char in allowed_chars for char in id_str)
