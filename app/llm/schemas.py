from typing import Optional
from pydantic import BaseModel, Field


class CVSchema(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)


class InvoiceSchema(BaseModel):
    invoice_number: Optional[str] = None
    vendor: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    total: Optional[str] = None


class ReceiptSchema(BaseModel):
    merchant: Optional[str] = None
    date: Optional[str] = None
    total: Optional[str] = None
    payment_method: Optional[str] = None


class ContractSchema(BaseModel):
    parties: list[str] = Field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    signature_status: Optional[str] = None


SCHEMA_MAP = {
    "cv": CVSchema,
    "invoice": InvoiceSchema,
    "receipt": ReceiptSchema,
    "contract": ContractSchema,
}