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


def format_center(text: str):
    return f"<div style='text-align: center'>{text}</div>"

def format_style(text: str, color: str):
    return f"<span class='highlight {color}'>{text}</span>"

TIME_NOT_SET = "N/A"
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

    @classmethod
    def dtypes(cls):
        return {
            cls.ID: int,
            cls.LICENCE_PLATE: str,
        }


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
def load_events(filename,
                columns_name_mapping):
    events = defaultdict(VehicleLogs)

    try:
        df = pd.read_csv(filename)
        df.rename(columns=columns_name_mapping, inplace = True)
        df.set_index(VehicleJournalTable.ID)
        df = sort_by_check_out_time(df, ascending=True)
        df = df.astype(VehicleJournalTable.dtypes())

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

            events[row[VehicleJournalTable.LICENCE_PLATE]].add(VehicleLogItem(time_check_in,
                                                                   time_check_out))
    except pd.errors.EmptyDataError as e:
        pass
    return events, df


def events_to_df(events, df):
    events_df = []
    for _, row in df.iterrows():
        logs = events[row[VehicleJournalTable.LICENCE_PLATE]]
        for record in logs:
            info = deepcopy(row)
            info[VehicleJournalTable.TIME_CHECK_IN] = TIME_NOT_SET
            info[VehicleJournalTable.TIME_CHECK_OUT] = TIME_NOT_SET
            if isinstance(record.check_in_time, datetime):
                info[VehicleJournalTable.TIME_CHECK_IN] = record.check_in_time.strftime(datetime_format)

            if isinstance(record.check_out_time, datetime):
                info[VehicleJournalTable.TIME_CHECK_OUT] = record.check_out_time.strftime(datetime_format)

            events_df.append(info)
    return events_df


class Page:
    VEHICLES = "Наряд"
    JOURNAL = "Журнал"

    @classmethod
    def items(cls):
        return [
            cls.VEHICLES, cls.JOURNAL
        ]


def display_vehicles_page(events,
                          vehicles,
                          skip_columns,
                          short_data_columns):
    display_columns = [c for c in vehicles.columns if c not in skip_columns]
    # print header of table
    sizes = [1] * len(display_columns)
    containers = st.columns(sizes)
    for i, column in enumerate(display_columns):
        # containers[i].write(column.capitalize())
        containers[i].markdown(format_center(column.capitalize()), unsafe_allow_html=True)
    st.markdown("""---""")

    # print table's rows
    containers = st.columns(sizes)
    indexes = {c:i for i, c in enumerate(display_columns)}
    vehicles_data = vehicles[short_data_columns]
    for _, row in vehicles_data.iterrows():
        idx = row[VehicleJournalTable.LICENCE_PLATE]
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
                    text = format_style(text, color)
            elif col == VehicleJournalTable.TIME_CHECK_OUT:
                text = "_"
                if events[idx].check_out_time:
                    text = events[idx].check_out_time.strftime(datetime_format)
                    if not events[idx].checked_in:
                        text = format_style(text, color)
            if len(events[idx]) > 0:
                # we highlight only specific columns
                if col not in [Controls.CHECK_IN,
                               Controls.CHECK_OUT,
                               VehicleJournalTable.TIME_CHECK_OUT,
                               VehicleJournalTable.TIME_CHECK_IN]:
                    text = format_style(text, color)

            containers[indexes[col]].markdown(format_center(text), unsafe_allow_html=True)

        st.markdown("""---""")


def main():

    st.set_page_config(layout="wide")

    local_css("style.css")

    # log_file = Path(f"logs/log_{datetime.now().strftime('%d-%m-%Y')}.csv")
    log_file = Path(f"logs/log.csv")

    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.touch(exist_ok=True)

    # st.header(Controls.HEADER)

    # read vehicles from file
    uploaded_file = st.sidebar.file_uploader(Controls.UPLOAD_FILE, type="xlsx")

    header = f"Наряд №0001 на {datetime.now().strftime('%d.%m.%Y')}"
    num_vehicles_total = None
    columns_name_mapping = {}
    if uploaded_file:
        # header = pd.read_excel(uploaded_file, usecols=[0], nrows=1)# .columns[0]
        columns_in_header = list(pd.read_excel(uploaded_file, nrows=1).columns)
        valid_columns = [c for c in columns_in_header if "Unnamed" not in str(c)]
        if len(valid_columns) == 1:
            header = valid_columns[0]
        elif len(valid_columns) > 2:
            header = valid_columns[2]
            num_vehicles_total = int(valid_columns[1])
        else:
            pass

        vehicles = pd.read_excel(uploaded_file,
                                 skiprows=1)
        columns_name_mapping = {col: col.lower() for col in vehicles.columns}
        vehicles.rename(columns=columns_name_mapping, inplace = True)
        vehicles.set_index(VehicleJournalTable.ID)
        vehicles = vehicles.astype(VehicleJournalTable.dtypes())

        # check duplicates
        license_plates = vehicles[VehicleJournalTable.LICENCE_PLATE]
        duplicated = license_plates[license_plates.duplicated()]
        if len(duplicated) > 0:
            st.error("Таблиця містить не унікальні номерні знаки. "
                     "Виправте, та перезавантажте таблицю, щоб продовжити")
            st.dataframe(duplicated)
            return
    else:
        return

    page = st.sidebar.radio("", Page.items())



    # load events from history (cache)
    # if 'events' not in st.session_state:
    events, events_vehicles = load_events(str(log_file),
                                          columns_name_mapping)
    st.sidebar.markdown("---")

    btn_load = st.sidebar.empty()

    # clear all button
    if st.sidebar.button(Controls.CLEAR_ALL):
        for e in events.values():
            e.clear()
            events_vehicles.drop(events_vehicles.index, inplace=True)

    # clear (checked-in) button
    if st.sidebar.button(Controls.CLEAR_CHECKED_IN):
        for e in events.values():
            e.clear_checked_in()
            events_vehicles = \
                events_vehicles[events_vehicles[VehicleJournalTable.TIME_CHECK_IN] == TIME_NOT_SET]

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

    if page == Page.VEHICLES:
        # st.markdown(f"<h1 style='text-align: center'> {header} </h1>", unsafe_allow_html=True)
        st.header(header)
        display_vehicles_page(events, vehicles, skip_columns, short_data_columns)

    # convert `events` to dataframe
    events_df = []
    events_df.extend(events_to_df(events, vehicles[data_columns]))

    vehicles_license_plates = set(vehicles[VehicleJournalTable.LICENCE_PLATE])
    events_df.extend(
        events_to_df(
            events,
            events_vehicles[~events_vehicles[VehicleJournalTable.LICENCE_PLATE].isin(vehicles_license_plates)]
        )
    )

    df = pd.DataFrame(events_df, columns=data_columns)

    # sort by time
    df = sort_by_check_out_time(df)
    df.reset_index(drop=True, inplace=True)
    df.rename(columns={v: k for k, v in columns_name_mapping.items()}, inplace=True)

    df.to_csv(str(log_file), index=False)

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

    num_checked_out = sum([len(logs) > 0 and not logs.checked_in for logs in events.values()])
    num_vehicles_total = num_vehicles_total or len(vehicles)

    st.sidebar.subheader("Кількість")
    vehicle_counts = {
        "За списком": num_vehicles_total,
        "На виїзді": num_checked_out,
        "В наявності": num_vehicles_total - num_checked_out,
    }
    columns = st.sidebar.columns(2)
    for (k, v) in vehicle_counts.items():
        columns[0].text(k)
        columns[1].text(v)


    # display table
    if page == Page.JOURNAL:
        st.header(f"Журнал [{len(df)}]")

        inv_columns_name_mapping = {v: k for k, v in columns_name_mapping.items()}
        df.reset_index(drop=True, inplace=True)
        for c in df.columns:
            df[c] = df[c].astype(str)
        st.dataframe(df[[inv_columns_name_mapping[c] for c in short_data_columns]])

main()

