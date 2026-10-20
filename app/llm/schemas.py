
from pydantic import BaseModel, Field


class CVSchema(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    skills: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)


class InvoiceSchema(BaseModel):
    invoice_number: str | None = None
    vendor: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    total: str | None = None


class ReceiptSchema(BaseModel):
    merchant: str | None = None
    date: str | None = None
    total: str | None = None
    payment_method: str | None = None
    expense_category: str | None = None


class ContractSchema(BaseModel):
    parties: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    signature_status: str | None = None


SCHEMA_MAP = {
    "cv": CVSchema,
    "invoice": InvoiceSchema,
    "receipt": ReceiptSchema,
    "contract": ContractSchema,
}