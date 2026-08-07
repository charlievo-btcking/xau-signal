"""
Nơi cất nhật ký tín hiệu.

Streamlit Cloud xoá sạch ổ đĩa mỗi lần khởi động lại, nên file CSV không sống
được ở đó. Khi có thông tin Google Sheets trong secrets, app tự chuyển sang ghi
lên Sheets; không có thì quay về CSV cho máy cá nhân.
"""
import os
from typing import Optional

import pandas as pd

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class CSVStore:
    kind = "csv"

    def __init__(self, path: str):
        self.path = path

    @property
    def label(self) -> str:
        return f"CSV cục bộ · {os.path.basename(self.path)}"

    def read(self) -> Optional[pd.DataFrame]:
        if not os.path.exists(self.path):
            return None
        return pd.read_csv(self.path)

    def write(self, df: pd.DataFrame) -> None:
        df.to_csv(self.path, index=False)


class SheetsStore:
    kind = "sheets"

    def __init__(self, info: dict, sheet_name: str, worksheet: str):
        import gspread
        from google.oauth2.service_account import Credentials

        creds = Credentials.from_service_account_info(dict(info), scopes=SCOPES)
        self._gc = gspread.authorize(creds)
        self.sheet_name = sheet_name
        self.worksheet = worksheet
        self.email = dict(info).get("client_email", "")
        self._ws = None

    @property
    def label(self) -> str:
        return f"Google Sheets · {self.sheet_name}/{self.worksheet}"

    def _sheet(self):
        if self._ws is not None:
            return self._ws
        import gspread
        try:
            sh = self._gc.open(self.sheet_name)
        except gspread.SpreadsheetNotFound:
            raise RuntimeError(
                f"Không tìm thấy bảng tính '{self.sheet_name}'. Hãy tạo nó trên Google "
                f"Drive rồi chia sẻ quyền Editor cho {self.email}")
        try:
            self._ws = sh.worksheet(self.worksheet)
        except gspread.WorksheetNotFound:
            self._ws = sh.add_worksheet(self.worksheet, rows=2000, cols=30)
        return self._ws

    def read(self) -> Optional[pd.DataFrame]:
        rows = self._sheet().get_all_values()
        if not rows or len(rows) < 2:
            return None
        return pd.DataFrame(rows[1:], columns=rows[0]).replace("", pd.NA)

    def write(self, df: pd.DataFrame) -> None:
        out = df.copy()
        for c in out.columns:
            out[c] = out[c].astype(object).where(out[c].notna(), "").astype(str)
        self._sheet().clear()
        self._sheet().update([out.columns.tolist()] + out.values.tolist())


def get_store(cfg):
    """Tự chọn nơi lưu. Có secrets Google thì dùng Sheets, không thì dùng CSV."""
    try:
        import streamlit as st
        info = st.secrets.get("gcp_service_account", None)
        if info:
            return SheetsStore(info,
                               st.secrets.get("GSHEET_NAME", cfg.sheet_name),
                               st.secrets.get("GSHEET_WORKSHEET", cfg.sheet_worksheet))
    except Exception as e:
        try:
            import streamlit as st
            st.sidebar.warning(f"Không dùng được Google Sheets: {e}")
        except Exception:
            pass
    return CSVStore(cfg.journal_path)
