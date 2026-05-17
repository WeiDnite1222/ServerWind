import yaml

def yaml_parser(yaml_filepath):
    """
    :INFO: Read yaml file. (Use method safe_load instead of the unsafe "load" method)
    讀取YAML檔案 (使用safe_load而不是load來避免可能的安全隱患)

    :WARN: You may need call this func within try-except block to avoid unexpected errors.
    警告>你可能會在呼叫此函式時需要將其(呼叫代碼)包裝在try-except(錯誤處理)裡來避免例外情況發生。
    """
    with open(yaml_filepath, 'r') as f:
        data = yaml.safe_load(f)
        f.close()
        return data


def yaml_writer(target_yaml_filepath, new_yaml_data, indent=4) -> None:
    """
    Write new data to yaml file.

    :WARN: You may need call this func within try-except block to avoid unexpected errors.
    警告>你可能會在呼叫此函式時需要將其(呼叫代碼)包裝在try-except(錯誤處理)裡來避免例外情況發生。
    """

    with open(target_yaml_filepath, 'w') as f:
        yaml.dump(new_yaml_data, f, indent=indent)
        f.close()
        return
