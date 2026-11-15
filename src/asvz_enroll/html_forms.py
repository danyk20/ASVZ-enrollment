"""Reads the forms of a web page, so the app can fill them in like a browser would."""

from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


@dataclass(frozen=True)
class HtmlForm:
    submit_url: str
    fields: dict[str, str]
    submit_button_name: str | None

    def asks_for(self, field_name: str) -> bool:
        return field_name in self.fields

    def filled_in_with(self, answers: dict[str, str]) -> dict[str, str]:
        """The data a browser would send: the form's own fields, our answers, the button."""
        data = self.fields | answers
        if self.submit_button_name:
            data[self.submit_button_name] = ""
        return data


def find_forms(html: str, page_url: str) -> list[HtmlForm]:
    page = BeautifulSoup(html, "html.parser")
    return [_read_form(form, page_url) for form in page.find_all("form")]


def page_title(html: str) -> str:
    title = BeautifulSoup(html, "html.parser").title
    return title.get_text(strip=True) if title else "(page without title)"


def _read_form(form: Tag, page_url: str) -> HtmlForm:
    fields = {
        _attribute(field, "name"): _attribute(field, "value")
        for field in form.find_all("input")
        if _attribute(field, "name") and _attribute(field, "type") != "submit"
    }
    return HtmlForm(
        submit_url=urljoin(page_url, _attribute(form, "action")),
        fields=fields,
        submit_button_name=_name_of_submit_button(form),
    )


def _name_of_submit_button(form: Tag) -> str | None:
    for button in form.find_all(["button", "input"]):
        if _attribute(button, "type") == "submit" and _attribute(button, "name"):
            return _attribute(button, "name")
    return None


def _attribute(tag: Tag, name: str) -> str:
    value = tag.get(name)
    return value if isinstance(value, str) else ""
