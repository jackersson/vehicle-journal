from collections import defaultdict
import typing as typ
import io
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import streamlit as st


def local_css(file_name):
    with open(file_name) as f:
        st.markdown('<style>{}</style>'.format(f.read()), unsafe_allow_html=True)


class VehicleJournalTable:
    ID = "№"
    VEHICLE_MODEL = "марка машини"
    LICENCE_PLATE = "номерний знак"
    GROUP_OF_OPERATION = "група експлуатації"
    VEHICLE_PURPOSE = "з якою метою призначається машина"
    ROUTE = "маршрут руху"
    RESPONSIBLE = "в чиє розпорядження"
    TIME_CHECK_OUT = "час виїзду"
    TIME_CHECK_IN = "час повернення"


class Controls:
    CHECK_OUT = "Виїхала"
    CHECK_IN = "Повернулась"

    HEADER = "Транспортні засоби"
    UPLOAD_FILE = "Обрати файл"
    DOWNLOAD = "Завантажити (журнал)"
    CLEAR_ALL = "Очистити (все)"
    CLEAR_CHECKED_IN = "Очистити (повернулись)"


@dataclass
class VehicleLogItem:
    _check_in_time: datetime = None
    _check_out_time: datetime = None

    def check_in(self, time: datetime = None):
        self._check_in_time = time or datetime.now()
        return self

    def check_out(self, time: datetime = None):
        self._check_out_time = time or datetime.now()
        return self

    @property
    def check_in_time(self):
        return self._check_in_time

    @property
    def check_out_time(self):
        return self._check_out_time

    @property
    def checked_in(self):
        return isinstance(self._check_in_time, datetime)


class VehicleLogs:

    def __init__(self) -> None:
        self._logs: typ.List[VehicleLogItem] = list()

    def check_in(self, time: datetime = None):
        if self.last:
            self.last.check_in(time)

    def check_out(self, time: datetime = None):
        if self.last and not self.last.checked_in:
            self.last.check_in(time)

        self._logs.append(VehicleLogItem().check_out(time))

    def clear_checked_in(self):
        logs = [self.last] if self.last else []
        self._logs = logs + [l for l in self._logs[:-1] if not l.checked_in]

    def clear(self):
        self._logs = [self.last] if self.last else []

    @property
    def check_in_time(self):
        return self.last.check_in_time if self.last else None

    @property
    def check_out_time(self):
        return self.last.check_out_time if self.last else None

    @property
    def checked_in(self):
        return self.last.checked_in if self.last else True

    @property
    def last(self):
        return self._logs[-1] if len(self._logs) > 0 else None

    def __len__(self):
        return len(self._logs)

    def __iter__(self):
        for l in self._logs:
            yield l


def main():
    datetime_format = "%H:%M:%S %d.%m.%Y"

    st.set_page_config(layout="wide")

    local_css("style.css")

    # load events from history (cache)
    if 'events' not in st.session_state:
        st.session_state['events'] = defaultdict(VehicleLogs)
    events = st.session_state['events']

    # column size for `ui element`
    ui_elements = {
        Controls.HEADER: 5,
        Controls.DOWNLOAD: 1,
        Controls.CLEAR_ALL: 1,
        Controls.CLEAR_CHECKED_IN: 1,
    }

    # prepare containers
    ordered_elements = [Controls.HEADER,
                        Controls.DOWNLOAD,
                        Controls.CLEAR_ALL, Controls.CLEAR_CHECKED_IN]
    elements_indexes = {elem: i for i, elem in enumerate(ordered_elements)}
    ctrl_containers = st.columns([ui_elements[elem] for elem in ordered_elements])

    # header title
    elem_name = Controls.HEADER
    ctrl_containers[elements_indexes[elem_name]].header(elem_name)

    # clear all button
    elem_name = Controls.CLEAR_ALL
    if ctrl_containers[elements_indexes[elem_name]].button(elem_name):
        for e in events.values():
            e.clear()

    # clear (checked-in) button
    elem_name = Controls.CLEAR_CHECKED_IN
    if ctrl_containers[elements_indexes[elem_name]].button(elem_name):
        for e in events.values():
            e.clear_checked_in()

    # read vehicles from file
    uploaded_file = st.sidebar.file_uploader(Controls.UPLOAD_FILE, type="xlsx")
    if uploaded_file:
        vehicles = pd.read_excel(uploaded_file,
                                 converters={VehicleJournalTable.ID: int})

        vehicles.set_index(VehicleJournalTable.ID)
    else:
        return


    skip_columns = set([VehicleJournalTable.GROUP_OF_OPERATION,
                        VehicleJournalTable.VEHICLE_PURPOSE])

    # add columns for state (`check_in`, `check_out`)
    data_columns = list(vehicles.columns)
    short_data_columns = [c for c in data_columns if c not in skip_columns]
    for i, (column, control) in enumerate(
            zip([VehicleJournalTable.TIME_CHECK_OUT,
                VehicleJournalTable.TIME_CHECK_IN],
                [Controls.CHECK_OUT, Controls.CHECK_IN])):
        vehicles.insert(list(vehicles.columns).index(column),
                        control, [bool(i)] * len(vehicles))

    display_columns = [c for c in vehicles.columns if c not in skip_columns]

    # print header of table
    sizes = [1] + [3] * (len(display_columns) - 1)
    containers = st.columns(sizes)
    for i, column in enumerate(display_columns):
        containers[i].write(column.capitalize())
    st.markdown("""---""")

    # print table's rows
    containers = st.columns(sizes)
    indexes = {c:i for i, c in enumerate(display_columns)}

    vehicles_data = vehicles[short_data_columns]
    for idx, row in vehicles_data.iterrows():
        containers = st.columns(sizes)

        # check-out button p
        column_type = Controls.CHECK_OUT
        if containers[indexes[column_type]].button(column_type,
                                               key=f"{column_type}:{idx}"):
            events[idx].check_out()

        column_type = Controls.CHECK_IN
        if containers[indexes[column_type]].button(column_type,
                                               key=f"{column_type}:{idx}"):
            events[idx].check_in()

        color = 'green' if events[idx].checked_in else 'red'
        for col in vehicles_data.columns:
            text = row[col]
            if col == VehicleJournalTable.TIME_CHECK_IN:
                text = "_"
                if events[idx].check_in_time:
                    text = events[idx].check_in_time.strftime(datetime_format)
                    text = f"<div><span class='highlight {color}'>{text}</span> </div>"
            elif col == VehicleJournalTable.TIME_CHECK_OUT:
                text = "_"
                if events[idx].check_out_time:
                    text = events[idx].check_out_time.strftime(datetime_format)
                    if not events[idx].checked_in:
                        text = f"<div><span class='highlight {color}'>{text}</span> </div>"

            if len(events[idx]) > 0:
                # we highlight only specific columns
                if col not in [Controls.CHECK_IN,
                               Controls.CHECK_OUT,
                               VehicleJournalTable.TIME_CHECK_OUT,
                               VehicleJournalTable.TIME_CHECK_IN]:
                    text = f"<div><span class='highlight {color}'>{text}</span> </div>"

            containers[indexes[col]].markdown(text, unsafe_allow_html=True)

        st.markdown("""---""")

    st.header("Журнал")

    # convert `events` to dataframe
    events_df = []
    for idx, row in vehicles[data_columns].iterrows():
        logs = events[idx]
        for record in logs:
            info = deepcopy(row)
            info[VehicleJournalTable.TIME_CHECK_IN] = "N/A"
            info[VehicleJournalTable.TIME_CHECK_OUT] = "N/A"
            if isinstance(record.check_in_time, datetime):
                info[VehicleJournalTable.TIME_CHECK_IN] = record.check_in_time.strftime(datetime_format)

            if isinstance(record.check_out_time, datetime):
                info[VehicleJournalTable.TIME_CHECK_OUT] = record.check_out_time.strftime(datetime_format)

            events_df.append(info)

    df = pd.DataFrame(events_df, columns=data_columns)

    # sort by time
    check_out_df_column = f"{VehicleJournalTable.TIME_CHECK_OUT}_dt"
    df[check_out_df_column] = pd.to_datetime(df[VehicleJournalTable.TIME_CHECK_OUT])
    df = df.sort_values(by=check_out_df_column, ascending=False)
    df.drop(columns=check_out_df_column, inplace=True)
    df.reset_index(drop=True, inplace=True)

    # convert to Excel and Save to file
    with io.BytesIO() as buffer:
        with pd.ExcelWriter(buffer) as writer:
            # Convert the dataframe to an XlsxWriter Excel object.
            df.to_excel(writer, index=False, sheet_name='Журнал')

            # Auto-adjust columns' width
            for column in df:
                column_width = max(df[column].astype(str).map(len).max(), len(column))
                col_idx = df.columns.get_loc(column)
                writer.sheets['Журнал'].set_column(col_idx, col_idx, column_width)

        elem_name = Controls.DOWNLOAD
        ctrl_containers[elements_indexes[elem_name]].download_button(
            label=elem_name,
            data=buffer.getvalue(),
            file_name=f"events_{datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.xlsx",
            mime="application/vnd.ms-excel",
            disabled=len(df) <= 0
        )

    # display table
    df.reset_index(drop=True, inplace=True)
    st.dataframe(df[short_data_columns])

main()

