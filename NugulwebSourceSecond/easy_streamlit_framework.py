import os
import json
import streamlit as st
import pandas as pd
from api_client import APIClient

class PropertyLoader:
    def __init__(self, json_name: str):
        self.properties = self.load_properties(json_name)

    def load_properties(self, json_name: str) -> dict:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        messages_path = os.path.join(base_dir, json_name)
        with open(messages_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_property(self, path: str, default=None):
        keys = path.split('.')
        result = self.properties
        for key in keys:
            if isinstance(result, dict) and key in result:
                result = result[key]
            else:
                return default
        return result

class UtilRenderer:
    @st.dialog("Result")
    def show_message(message, msg_type):
        if msg_type == "success":
            st.success(message)
        elif msg_type == "error":
            st.error(message)

class FormRenderer:
    def __init__(self, form_loader: 'PropertyLoader'):
        self.form_loader = form_loader
        self.api_url = st.secrets["API_URL"]

    def render(self, path: str, value_dict: dict = {}) -> dict:
        form_structure = self.form_loader.get_property(path)
        if not isinstance(form_structure, dict):
            return None

        send_list = {}
        errors = {}
        dependencies = {}

        # 필드 의존성 관리
        for item_name, properties in form_structure.items():
            if 'dependencies' in properties:
                dependencies[item_name] = properties['dependencies']

        # form 안에 요소를 그룹화하여 렌더링
        with st.form(key=path):
            for item_name, properties in form_structure.items():
                label = properties.get('label', item_name)
                value = value_dict.get(item_name, properties.get('default_value', ""))
                
                # 의존성이 있는 selectbox의 경우 옵션을 동적으로 설정
                if item_name in dependencies:
                    dependency_info = dependencies[item_name]
                    dependent_field = list(dependency_info.keys())[0]
                    selected_value = value_dict.get(dependent_field, "")
                    options = dependency_info[dependent_field].get(selected_value, [])
                    
                    # render_input을 사용하여 필드를 렌더링하고, 값을 send_list에 저장
                    send_list[item_name] = self.render_input(label, properties, value, options)
                    
                    # 콜백으로 페이지를 다시 렌더링
                    if st.selectbox(label, options, index=options.index(value) if value in options else 0, key=item_name) != value:
                        value_dict[item_name] = value
                        st.rerun()  # 페이지를 다시 렌더링
                else:
                    # 조건부 렌더링 체크
                    if 'conditional_render' in properties:
                        condition = properties['conditional_render']
                        dependent_value = value_dict.get(condition['field'])
                        if dependent_value != condition['value']:
                            continue

                    # 기본적으로 필드를 렌더링
                    send_list[item_name] = self.render_input(label, properties, value)

                # 필수 입력 필드에 대한 유효성 검사
                if properties.get('required', False) and not send_list[item_name]:
                    errors[item_name] = properties.get('required_error_message', f"{label}은(는) 필수 입력 항목입니다.")

            # 제출 버튼 추가 (st.form 블록 내부에 위치)
            submitted = st.form_submit_button(label="제출")

        # 제출 버튼이 눌렸을 때 유효성 검사 처리
        if submitted:
            if errors:
                for error_msg in errors.values():
                    st.error(error_msg)
                return None  # 유효성 검사 실패 시 반환하지 않음
            else:
                return send_list  # 유효성 검사 통과 시 결과 반환
        else:
            return None

    def render_input(self, label: str, properties: dict, value=None, options=None):
        input_type = properties['input_type']
        help_text = properties.get('help', None)

        if input_type == 'selectbox':
            options = options or properties.get('item_type_options', [])

            if isinstance(options, dict):
                api_path = options['api_path']
                data = options['data']
                value_column = options['value_column']
                collection_name = options['collection_name']

                new_options = list()

                for k, v in data.items():
                    if isinstance(v, str) and "session." in v:
                        key_of_state = v.replace("session.", "")
                        data[k] = st.session_state[key_of_state]

                api = APIClient(self.api_url)
                data_list = api.make_request(api_path, data=data)
                data_list = data_list.get(collection_name + "_list")

                for d in data_list:
                    new_options.append(d.get(value_column))
                    
                options = new_options
                
            # 값이 유효한지 검사하고 기본값 설정
            if not value or value not in options:
                index = 0
            else:
                index = options.index(value)

            return st.selectbox(label, options, index=index, help=help_text)
        elif input_type == 'text_input':
            return st.text_input(label, value=str(value), help=help_text)
        elif input_type == 'password':
            return st.text_input(label, value=str(value), help=help_text, type='password')
        elif input_type == 'checkbox':
            return st.checkbox(label, value=bool(value), help=help_text)
        elif input_type == 'number_input':
            min_value = properties.get('min_value', 0)
            max_value = properties.get('max_value', None)

            try:
                min_value = int(min_value)
            except ValueError:
                min_value = 0

            if max_value is not None:
                try:
                    max_value = int(max_value)
                except ValueError:
                    max_value = None

            try:
                value = float(value) if '.' in str(value) else int(value)
            except ValueError:
                value = min_value

            return st.number_input(label, min_value=min_value, value=value, max_value=max_value, help=help_text)
        elif input_type == 'text_area':
            return st.text_area(label, value=str(value), help=help_text)
        elif input_type == 'multiselect':
            options = options or properties.get('item_type_options', [])

            if isinstance(options, dict):
                api_path = options['api_path']
                data = options['data']
                value_column = options['value_column']
                collection_name = options['collection_name']

                new_options = list()

                for k, v in data.items():
                    if isinstance(v, str) and "session." in v:
                        key_of_state = v.replace("session.", "")
                        data[k] = st.session_state[key_of_state]

                api = APIClient(self.api_url)
                data_list = api.make_request(api_path, data=data)
                data_list = data_list.get(collection_name + "_list")

                for d in data_list:
                    new_options.append(d.get(value_column))
                    
                options = new_options
                
            # 값이 유효한지 검사하고 기본값 설정
            value = [v for v in value if v in options]
            if not value:
                value = []

            return st.multiselect(label, options, default=value, help=help_text)

        return None





class DataEditorRenderer:
    def __init__(self, table_loader: PropertyLoader):
        self.table_loader = table_loader

    def render(self, path: str, value_df: pd.DataFrame) -> pd.DataFrame:
        table_properties = self.table_loader.get_property(path)  # 수정된 부분
        if not isinstance(table_properties, dict):
            return None

        column_config = self.build_column_config(table_properties, value_df.columns)
        return st.data_editor(
            value_df,
            use_container_width=True,
            hide_index=True,
            column_config=column_config
        )

    def build_column_config(self, table_properties: dict, columns: list) -> dict:
        column_config = {}
        for item_name, properties in table_properties.items():
            label = properties.get('label', item_name)
            col_type = properties.get('column_type', "text")

            width = properties.get('width', "small")
            if width not in ["small", "medium", "large"]:
                width = "small"
            required = properties.get('required', False)
            if not isinstance(required, bool):
                required = False
            disabled = properties.get('disabled', True)
            if not isinstance(disabled, bool):
                disabled = True

            # 컬럼 타입에 따라 설정
            column_config[item_name] = self.get_column_config(
                col_type, label, width, required, disabled, properties
            )

        # 테이블의 컬럼 중 설정되지 않은 컬럼을 숨김 처리
        for none_col in columns:
            if none_col not in table_properties:
                column_config[none_col] = None

        return column_config

    def get_column_config(self, col_type: str, label: str, width: str, required: bool, disabled: bool, properties: dict):
        if col_type == "text":
            return st.column_config.TextColumn(
                label=label,
                width=width,
                required=required,
                disabled=disabled
            )
        elif col_type == "number":
            max_value = properties.get('max_value', None)
            min_value = properties.get('min_value', 0)

            if not isinstance(max_value, int):
                max_value = None
            if not isinstance(min_value, int):
                min_value = 0

            return st.column_config.NumberColumn(
                label=label,
                width=width,
                required=required,
                disabled=disabled,
                min_value=min_value,
                max_value=max_value
            )
        elif col_type == "checkbox":
            return st.column_config.CheckboxColumn(
                label=label,
                width=width,
                required=required,
                disabled=disabled
            )
        elif col_type == "photo":
            return st.column_config.ImageColumn(
                label=label,
                width=width
            )
        return None