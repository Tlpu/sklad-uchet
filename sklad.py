# -*- coding: utf-8 -*-
"""
Учёт стройматериалов на складе.
Графический интерфейс: PyQt6. База данных: SQLite (файл sklad.db).
Три вкладки: Склад, Приход и расход, Отчёт.
"""

import sys
import sqlite3

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QTableWidget, QTableWidgetItem, QPushButton, QLineEdit,
    QComboBox, QSpinBox, QMessageBox, QGroupBox, QLabel,
)
from PyQt6.QtCore import Qt


# ============================ РАБОТА С БАЗОЙ ДАННЫХ ============================

DB_NAME = "sklad.db"


def get_connection():
    """Возвращает новое подключение к базе данных SQLite."""
    return sqlite3.connect(DB_NAME)


def init_db():
    """Создаёт таблицы, если их ещё нет, и наполняет демо-данными."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS materials (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT NOT NULL UNIQUE,
            unit     TEXT NOT NULL,
            quantity REAL NOT NULL DEFAULT 0
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS operations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER NOT NULL,
            op_type     TEXT NOT NULL,
            amount      REAL NOT NULL,
            comment     TEXT,
            created     TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (material_id) REFERENCES materials (id)
        )
        """
    )
    conn.commit()

    # Демо-данные добавляем только один раз — в пустую базу.
    cur.execute("SELECT COUNT(*) FROM materials")
    if cur.fetchone()[0] == 0:
        seed_demo_data(cur)
        conn.commit()
    conn.close()


def seed_demo_data(cur):
    """Наполняет базу примерами стройматериалов и операций."""
    demo_materials = [
        ("Цемент М500 (мешок 50 кг)", "мешок", 120),
        ("Песок карьерный", "м3", 45),
        ("Щебень фракции 20-40", "м3", 30),
        ("Кирпич керамический одинарный", "шт", 8500),
        ("Арматура А500С д.12", "м", 640),
        ("Доска обрезная 50х150", "м3", 12),
        ("Гипсокартон 12,5 мм", "лист", 210),
        ("Краска интерьерная белая", "л", 95),
    ]
    for name, unit, qty in demo_materials:
        cur.execute(
            "INSERT INTO materials (name, unit, quantity) VALUES (?, ?, ?)",
            (name, unit, qty),
        )

    demo_operations = [
        (1, "приход", 100, "Завоз от поставщика ООО 'СтройБаза'"),
        (2, "приход", 20, "Завоз от поставщика ООО 'СтройБаза'"),
        (1, "расход", 35, "Выдача на объект: пр. Мира, д. 12 (кладка стен)"),
        (4, "расход", 1200, "Выдача на объект: пр. Мира, д. 12 (кладка стен)"),
        (5, "приход", 500, "Завоз арматуры, счёт №245 от ООО 'МеталлПром'"),
        (7, "расход", 60, "Монтаж перегородок, бригада №2"),
        (3, "расход", 10, "Отсыпка фундамента, объект пр. Мира, д. 12"),
        (8, "расход", 15, "Выдача маляру Иванову, отделка 2 этажа"),
        (6, "приход", 8, "Поступление доски, счёт №118 от ООО 'ЛесТорг'"),
        (1, "расход", 25, "Заливка стяжки, объект пр. Мира, д. 12"),
        (4, "расход", 800, "Выдача на объект: ул. Садовая, д. 5 (фасад)"),
    ]
    for material_id, op_type, amount, comment in demo_operations:
        cur.execute(
            "INSERT INTO operations (material_id, op_type, amount, comment) "
            "VALUES (?, ?, ?, ?)",
            (material_id, op_type, amount, comment),
        )


def get_all_materials():
    """Возвращает все материалы с остатками."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, unit, quantity FROM materials ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return rows


def add_material(name, unit):
    """Добавляет новый материал с нулевым остатком."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO materials (name, unit, quantity) VALUES (?, ?, 0)",
            (name, unit),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def delete_material(material_id):
    """Удаляет материал вместе с его операциями из журнала."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM operations WHERE material_id = ?", (material_id,))
    cur.execute("DELETE FROM materials WHERE id = ?", (material_id,))
    conn.commit()
    conn.close()


def run_operation(material_id, op_type, amount, comment):
    """Проводит операцию прихода или расхода. Возвращает текст ошибки."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT quantity FROM materials WHERE id = ?", (material_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        return "Материал не найден"
    quantity = row[0]
    if op_type == "расход" and amount > quantity:
        conn.close()
        return "Недостаточно материала на складе"
    if op_type == "приход":
        new_qty = quantity + amount
    else:
        new_qty = quantity - amount
    cur.execute("UPDATE materials SET quantity = ? WHERE id = ?", (new_qty, material_id))
    cur.execute(
        "INSERT INTO operations (material_id, op_type, amount, comment) VALUES (?, ?, ?, ?)",
        (material_id, op_type, amount, comment),
    )
    conn.commit()
    conn.close()
    return None


def get_recent_operations(limit=50):
    """Возвращает последние операции журнала с названиями материалов."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT o.created, m.name, o.op_type, o.amount, m.unit, o.comment
        FROM operations o
        JOIN materials m ON m.id = o.material_id
        ORDER BY o.id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


# ============================ ГЛАВНОЕ ОКНО И ВКЛАДКИ ============================

class MainWindow(QMainWindow):
    """Главное окно программы с тремя вкладками."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Учёт стройматериалов на складе")
        self.resize(760, 520)

        tabs = QTabWidget()
        tabs.addTab(self._make_warehouse_tab(), "Склад")
        tabs.addTab(self._make_operations_tab(), "Приход и расход")
        tabs.addTab(self._make_report_tab(), "Отчёт")
        self.setCentralWidget(tabs)

        self.refresh_warehouse()
        self.refresh_journal()
        self.refresh_material_combo()

    # --------------------------- Вкладка «Склад» ---------------------------

    def _make_warehouse_tab(self):
        """Создаёт вкладку со списком материалов и кнопками."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Наименование", "Ед. изм.", "Остаток"])
        self.table.setColumnWidth(1, 320)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Например: Гвозди 90 мм")
        self.unit_edit = QLineEdit()
        self.unit_edit.setPlaceholderText("Например: кг")
        form.addRow("Наименование:", self.name_edit)
        form.addRow("Единица измерения:", self.unit_edit)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        add_btn = QPushButton("Добавить материал")
        add_btn.clicked.connect(self.add_material_clicked)
        self.delete_btn = QPushButton("Удалить выбранное")
        self.delete_btn.clicked.connect(self.delete_selected)
        refresh_btn = QPushButton("Обновить таблицу")
        refresh_btn.clicked.connect(self.refresh_all)
        buttons.addWidget(add_btn)
        buttons.addWidget(self.delete_btn)
        buttons.addWidget(refresh_btn)
        layout.addLayout(buttons)

        return widget

    def refresh_warehouse(self):
        """Перезаполняет таблицу материалов актуальными данными."""
        materials = get_all_materials()
        self.table.setRowCount(len(materials))
        for row_index, (mid, name, unit, qty) in enumerate(materials):
            values = [str(mid), name, unit, str(qty)]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col in (0, 2, 3):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, col, item)

    def refresh_all(self):
        """Обновляет таблицы и список материалов на всех вкладках."""
        self.refresh_warehouse()
        self.refresh_journal()
        self.refresh_material_combo()

    def add_material_clicked(self):
        """Обрабатывает кнопку добавления нового материала."""
        name = self.name_edit.text().strip()
        unit = self.unit_edit.text().strip()
        if not name or not unit:
            QMessageBox.warning(self, "Ошибка", "Заполните наименование и единицу измерения")
            return
        if add_material(name, unit):
            self.name_edit.clear()
            self.unit_edit.clear()
            self.refresh_all()
            QMessageBox.information(self, "Готово", f"Материал «{name}» добавлен")
        else:
            QMessageBox.warning(self, "Ошибка", "Материал с таким названием уже есть")

    def delete_selected(self):
        """Удаляет материал, выбранный в таблице, с подтверждением."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите материал в таблице")
            return
        material_id = int(self.table.item(row, 0).text())
        name = self.table.item(row, 1).text()
        answer = QMessageBox.question(
            self,
            "Подтверждение",
            f"Удалить материал «{name}» вместе с историей операций?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        delete_material(material_id)
        self.refresh_all()
        QMessageBox.information(self, "Готово", f"Материал «{name}» удалён")

    # ------------------------ Вкладка «Приход и расход» ------------------------

    def _make_operations_tab(self):
        """Создаёт вкладку с формой операции и журналом."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        box = QGroupBox("Новая операция")
        form = QFormLayout(box)
        self.material_combo = QComboBox()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["приход", "расход"])
        self.amount_spin = QSpinBox()
        self.amount_spin.setRange(1, 1000000)
        self.comment_edit = QLineEdit()
        self.comment_edit.setPlaceholderText("Например: выдача на объект, ул. Садовая, д. 5")
        form.addRow("Материал:", self.material_combo)
        form.addRow("Тип операции:", self.type_combo)
        form.addRow("Количество:", self.amount_spin)
        form.addRow("Комментарий:", self.comment_edit)
        run_btn = QPushButton("Провести операцию")
        run_btn.clicked.connect(self.run_operation_clicked)
        form.addRow(run_btn)
        layout.addWidget(box)

        self.journal = QTableWidget()
        self.journal.setColumnCount(6)
        self.journal.setHorizontalHeaderLabels(
            ["Дата и время", "Материал", "Тип", "Кол-во", "Ед.", "Комментарий"]
        )
        self.journal.setColumnWidth(0, 160)
        self.journal.setColumnWidth(1, 260)
        self.journal.setColumnWidth(5, 240)
        self.journal.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.journal.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.journal)

        return widget

    def refresh_material_combo(self):
        """Перезаполняет выпадающий список материалов."""
        self.material_combo.clear()
        for mid, name, unit, qty in get_all_materials():
            self.material_combo.addItem(f"{name} ({unit})", userData=mid)

    def refresh_journal(self):
        """Перезаполняет таблицу журнала операций."""
        operations = get_recent_operations()
        self.journal.setRowCount(len(operations))
        for row_index, row_data in enumerate(operations):
            for col, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                self.journal.setItem(row_index, col, item)

    def run_operation_clicked(self):
        """Обрабатывает кнопку проведения операции."""
        index = self.material_combo.currentIndex()
        if index < 0:
            QMessageBox.warning(self, "Ошибка", "Нет ни одного материала на складе")
            return
        material_id = self.material_combo.itemData(index)
        op_type = self.type_combo.currentText()
        amount = self.amount_spin.value()
        comment = self.comment_edit.text().strip()

        error = run_operation(material_id, op_type, amount, comment)
        if error:
            QMessageBox.warning(self, "Ошибка", error)
            return
        self.comment_edit.clear()
        self.refresh_all()
        QMessageBox.information(self, "Готово", "Операция проведена")

    # --------------------------- Вкладка «Отчёт» ---------------------------

    def _make_report_tab(self):
        """Создаёт вкладку с отчётом об остатках."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info = QLabel(
            "Отчёт показывает остатки по всем материалам. "
            "Строки с нулевым остатком подсвечены красным."
        )
        layout.addWidget(info)

        self.report_table = QTableWidget()
        self.report_table.setColumnCount(4)
        self.report_table.setHorizontalHeaderLabels(
            ["Наименование", "Ед. изм.", "Остаток", "Статус"]
        )
        self.report_table.setColumnWidth(0, 320)
        self.report_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.report_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.report_table)

        refresh_btn = QPushButton("Обновить отчёт")
        refresh_btn.clicked.connect(self.refresh_report)
        layout.addWidget(refresh_btn)

        self.refresh_report()
        return widget

    def refresh_report(self):
        """Перезаполняет таблицу отчёта и подсвечивает пустые позиции."""
        materials = get_all_materials()
        self.report_table.setRowCount(len(materials))
        for row_index, (mid, name, unit, qty) in enumerate(materials):
            status = "Достаточно" if qty > 0 else "Закончился"
            values = [name, unit, str(qty), status]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col >= 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if qty == 0:
                    item.setBackground(Qt.GlobalColor.red)
                self.report_table.setItem(row_index, col, item)


def main():
    """Точка входа: создаёт базу и запускает интерфейс."""
    init_db()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
