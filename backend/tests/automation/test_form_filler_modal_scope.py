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
    ):
        self.label = label
        self.field_type = field_type
        self.enabled = enabled
        self.visible = visible
        self.required = required
        self.value = None

    async def get_attribute(self, name: str):
        mapping = {
            "aria-label": self.label,
            "type": self.field_type,
            "id": self.label.lower().replace(" ", "-"),
            "required": "true" if self.required else None,
            "aria-required": "true" if self.required else None,
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


class FakeContainer:
    def __init__(self, text_inputs=None, selects=None, fieldsets=None, checkboxes=None):
        self.text_inputs = text_inputs or []
        self.selects = selects or []
        self.fieldsets = fieldsets or []
        self.checkboxes = checkboxes or []

    async def query_selector_all(self, selector: str):
        if selector.startswith('input[type="text"]'):
            return self.text_inputs
        if selector == "select":
            return self.selects
        if selector == "fieldset":
            return self.fieldsets
        if selector == 'input[type="checkbox"]':
            return self.checkboxes
        return []


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


@pytest.mark.asyncio
async def test_unresolved_required_field_is_reported():
    filler = FormFiller()
    filler.form_answers = {"email": "away@example.com"}
    modal = FakeContainer(text_inputs=[FakeElement("Work authorization", required=True)])

    result = await filler.detect_and_fill_fields(modal)

    assert result["resolved_fields"] == []
    assert result["unresolved_fields"] == ["Work authorization"]
    assert result["validation_errors"] == []
