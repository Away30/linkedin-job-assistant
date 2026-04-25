import pytest

from app.automation.form_filler import FormFiller


class FakeElement:
    def __init__(
        self,
        label: str,
        field_type: str = "text",
        enabled: bool = True,
        visible: bool = True,
        required: bool = False,
        readonly: bool = False,
        aria_label: str | None = None,
        element_id: str | None = None,
    ):
        self.label = label
        self.field_type = field_type
        self.enabled = enabled
        self.visible = visible
        self.required = required
        self.readonly = readonly
        self.aria_label = aria_label if aria_label is not None else label
        self.element_id = element_id or self.label.lower().replace(" ", "-")
        self.value = None

    async def get_attribute(self, name: str):
        mapping = {
            "aria-label": self.aria_label,
            "type": self.field_type,
            "id": self.element_id,
            "required": "true" if self.required else None,
            "aria-required": "true" if self.required else None,
            "readonly": "true" if self.readonly else None,
            "aria-readonly": "true" if self.readonly else None,
        }
        return mapping.get(name)

    async def is_enabled(self):
        return self.enabled

    async def is_visible(self):
        return self.visible

    async def click(self):
        return None

    async def fill(self, value: str):
        self.value = value


class FakeLabel:
    def __init__(self, text: str):
        self.text = text

    async def inner_text(self):
        return self.text


class FakeCollection:
    def __init__(self, elements):
        self._elements = elements

    async def all(self):
        return self._elements

    @property
    def first(self):
        return self._elements[0]


class FakeOption:
    def __init__(self, value: str, text: str):
        self.value = value
        self.text = text

    async def inner_text(self):
        return self.text

    async def get_attribute(self, name: str):
        if name == "value":
            return self.value
        return None


class FakeSelect(FakeElement):
    def __init__(self, label: str, options, **kwargs):
        super().__init__(label=label, field_type="select-one", **kwargs)
        self.options = options
        self.selected = None

    def locator(self, selector: str):
        if selector == "option":
            return FakeCollection(self.options)
        return FakeCollection([])

    async def select_option(self, value: str = None, label: str = None):
        if value is not None:
            self.selected = value
            return
        if label is not None:
            for option in self.options:
                if (await option.inner_text()) == label:
                    self.selected = option.value
                    return
        raise ValueError("option not found")


class FakeCheckbox(FakeElement):
    def __init__(self, label: str, checked: bool = False, **kwargs):
        super().__init__(label=label, field_type="checkbox", **kwargs)
        self.checked = checked

    async def is_checked(self):
        return self.checked

    async def click(self):
        self.checked = not self.checked


class FakeFieldset(FakeElement):
    def __init__(self, legend: str, radios, radio_labels: dict[str, str], **kwargs):
        super().__init__(label=legend, field_type="fieldset", **kwargs)
        self.legend = legend
        self.radios = radios
        self.radio_labels = radio_labels

    async def query_selector(self, selector: str):
        if selector.startswith("legend"):
            return FakeLabel(self.legend)
        return None

    def locator(self, selector: str):
        if selector == 'input[type="radio"]':
            return FakeCollection(self.radios)
        if selector.startswith('label[for="'):
            radio_id = selector[len('label[for="'):-2]
            return FakeCollection([FakeLabel(self.radio_labels[radio_id])])
        return FakeCollection([])


class FakeContainer:
    def __init__(self, text_inputs=None, selects=None, fieldsets=None, checkboxes=None, labels=None):
        self.text_inputs = text_inputs or []
        self.selects = selects or []
        self.fieldsets = fieldsets or []
        self.checkboxes = checkboxes or []
        self.labels = labels or {}
        self.query_calls = 0

    async def query_selector_all(self, selector: str):
        self.query_calls += 1
        if selector.startswith('input[type="text"]'):
            return self.text_inputs
        if selector == "select":
            return self.selects
        if selector == "fieldset":
            return self.fieldsets
        if selector == 'input[type="checkbox"]':
            return self.checkboxes
        return []

    async def query_selector(self, selector: str):
        prefix = 'label[for="'
        if selector.startswith(prefix) and selector.endswith('"]'):
            field_id = selector[len(prefix):-2]
            if field_id in self.labels:
                return FakeLabel(self.labels[field_id])
        return None


@pytest.mark.asyncio
async def test_detect_and_fill_fields_uses_only_modal_container():
    filler = FormFiller()
    filler.form_answers = {"email": "away@example.com", "phone": "5551112222"}
    page_level_field = FakeElement("Phone")
    page = FakeContainer(text_inputs=[page_level_field])
    modal = FakeContainer(text_inputs=[FakeElement("Email")])

    result = await filler.detect_and_fill_fields(modal)

    assert result["resolved_fields"] == ["Email"]
    assert result["unresolved_fields"] == []
    assert page_level_field.value is None
    assert modal.query_calls > 0
    assert page.query_calls == 0


@pytest.mark.asyncio
async def test_unresolved_required_field_is_reported():
    filler = FormFiller()
    filler.form_answers = {"email": "away@example.com"}
    modal = FakeContainer(text_inputs=[FakeElement("Work authorization", required=True)])

    result = await filler.detect_and_fill_fields(modal)

    assert result["resolved_fields"] == []
    assert result["unresolved_fields"] == ["Work authorization"]
    assert result["validation_errors"] == []


@pytest.mark.asyncio
async def test_readonly_text_field_is_treated_as_non_editable():
    filler = FormFiller()
    filler.form_answers = {"email": "away@example.com"}
    readonly_field = FakeElement("Email", required=True, readonly=True)
    modal = FakeContainer(text_inputs=[readonly_field])

    result = await filler.detect_and_fill_fields(modal)

    assert result["resolved_fields"] == []
    assert result["unresolved_fields"] == []
    assert readonly_field.value is None


@pytest.mark.asyncio
async def test_detect_and_fill_fields_handles_select_radio_and_checkbox():
    filler = FormFiller()
    filler.form_answers = {
        "experience level": "Senior",
        "work model": "Remote",
        "agree to terms": "yes",
    }
    select = FakeSelect(
        "Experience Level",
        options=[FakeOption("junior", "Junior"), FakeOption("senior", "Senior")],
    )
    radio_yes = FakeElement("remote", field_type="radio", element_id="work-model-remote")
    radio_no = FakeElement("onsite", field_type="radio", element_id="work-model-onsite")
    fieldset = FakeFieldset(
        legend="Work Model",
        radios=[radio_yes, radio_no],
        radio_labels={
            "work-model-remote": "Remote",
            "work-model-onsite": "Onsite",
        },
    )
    checkbox = FakeCheckbox("Agree to terms", checked=False)
    modal = FakeContainer(selects=[select], fieldsets=[fieldset], checkboxes=[checkbox])

    result = await filler.detect_and_fill_fields(modal)

    assert result["resolved_fields"] == ["Experience Level", "Work Model", "Agree to terms"]
    assert result["unresolved_fields"] == []
    assert result["validation_errors"] == []
    assert select.selected == "senior"
    assert checkbox.checked is True


@pytest.mark.asyncio
async def test_numeric_zero_is_accepted_and_invalid_number_gets_validation_error():
    filler = FormFiller()
    filler.form_answers = {
        "years_of_experience": "0",
        "expected salary": "not-a-number",
    }
    years_input = FakeElement("Years of experience", field_type="number")
    salary_input = FakeElement("Expected salary", field_type="number", required=True)
    modal = FakeContainer(text_inputs=[years_input, salary_input])

    result = await filler.detect_and_fill_fields(modal)

    assert "Years of experience" in result["resolved_fields"]
    assert "Expected salary" in result["unresolved_fields"]
    assert any("Expected salary" in error for error in result["validation_errors"])
    assert years_input.value == "0"


@pytest.mark.asyncio
async def test_label_for_lookup_path_is_used_when_no_aria_label():
    filler = FormFiller()
    filler.form_answers = {"email": "away@example.com"}
    input_field = FakeElement("Email", aria_label=None, element_id="email-input")
    modal = FakeContainer(text_inputs=[input_field], labels={"email-input": "Email"})

    result = await filler.detect_and_fill_fields(modal)

    assert result["resolved_fields"] == ["Email"]
    assert input_field.value == "away@example.com"
