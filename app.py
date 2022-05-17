from collections import defaultdict
import typing as typ
import io
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st


datetime_format = "%H:%M:%S %d.%m.%Y"


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
    UPLOAD_FILE = "Обрати файл з транспортними засобами"
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
        self._logs = [l for l in self._logs if not l.checked_in]

    def clear(self):
        self._logs = []

    def add(self, item: VehicleLogItem):
        self._logs.append(item)

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

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}[logs={len(self)}]"

    def __str__(self) -> str:
        return f"{self.__class__.__name__}[logs={len(self)}]"

    def __len__(self):
        return len(self._logs)

    def __iter__(self):
        for l in self._logs:
            yield l


def sort_by_check_out_time(df: pd.DataFrame, ascending: bool = False):
    check_out_df_column = f"{VehicleJournalTable.TIME_CHECK_OUT}_dt"
    df[check_out_df_column] = pd.to_datetime(df[VehicleJournalTable.TIME_CHECK_OUT])
    df = df.sort_values(by=check_out_df_column, ascending=ascending)
    df.drop(columns=check_out_df_column, inplace=True)
    return df

# @st.cache(allow_output_mutation=True)
def load_events(filename):
    events = defaultdict(VehicleLogs)

    try:
        df = pd.read_csv(filename)
        df = sort_by_check_out_time(df, ascending=True)
        for _, row in df.iterrows():
            try:
                time_check_in = datetime.strptime(str(row[VehicleJournalTable.TIME_CHECK_IN]),
                                                  datetime_format)
            except ValueError as e:
                time_check_in = None
            try:
                time_check_out = datetime.strptime(str(row[VehicleJournalTable.TIME_CHECK_OUT]),
                                                   datetime_format)
            except ValueError as e:
                time_check_out = None

            events[row[VehicleJournalTable.ID]].add(VehicleLogItem(time_check_in,
                                                                   time_check_out))
    except pd.errors.EmptyDataError as e:
        pass
    return events


def main():

    st.set_page_config(layout="wide")

    local_css("style.css")

    # log_file = Path(f"logs/log_{datetime.now().strftime('%d-%m-%Y')}.csv")
    log_file = Path(f"logs/log.csv")

    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.touch(exist_ok=True)

    st.header(Controls.HEADER)

    # read vehicles from file
    uploaded_file = st.sidebar.file_uploader(Controls.UPLOAD_FILE, type="xlsx")
    if uploaded_file:
        vehicles = pd.read_excel(uploaded_file,
                                 converters={VehicleJournalTable.ID: int})

        vehicles.set_index(VehicleJournalTable.ID)
    else:
        return

    # load events from history (cache)
    # if 'events' not in st.session_state:
    events = load_events(str(log_file))

    st.sidebar.markdown("---")

    btn_load = st.sidebar.empty()

    # clear all button
    if st.sidebar.button(Controls.CLEAR_ALL):
        for e in events.values():
            e.clear()

    # clear (checked-in) button
    if st.sidebar.button(Controls.CLEAR_CHECKED_IN):
        for e in events.values():
            e.clear_checked_in()

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

    skip_columns.add(VehicleJournalTable.ID)
    display_columns = [c for c in vehicles.columns if c not in skip_columns]

    # print header of table
    sizes = [1] * len(display_columns)
    containers = st.columns(sizes)
    for i, column in enumerate(display_columns):
        containers[i].write(column.capitalize())
    st.markdown("""---""")

    # print table's rows
    containers = st.columns(sizes)
    indexes = {c:i for i, c in enumerate(display_columns)}

    vehicles_data = vehicles[short_data_columns]
    for _, row in vehicles_data.iterrows():
        idx = row[VehicleJournalTable.ID]
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
            if col in skip_columns:
                continue

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


    # convert `events` to dataframe
    events_df = []
    for _, row in vehicles[data_columns].iterrows():
        logs = events[row[VehicleJournalTable.ID]]
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
    df = sort_by_check_out_time(df)
    df.reset_index(drop=True, inplace=True)

    df.to_csv(str(log_file), index=False)

    st.header(f"Журнал [{len(df)}]")

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
        btn_load.download_button(
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

