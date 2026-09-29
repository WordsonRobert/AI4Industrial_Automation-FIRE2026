use modbus::{Client, Coil};
use modbus::tcp::{self, Config};

const MODBUS_SERVER_IP: &str = "127.0.0.1";
const MODBUS_PORT: u16 = 502;
const UNIT_ID: u8 = 1;

struct ModbusClient {
    client: tcp::Transport,
}

impl ModbusClient {
    fn new() -> Self {
        let cfg = Config { tcp_port: MODBUS_PORT, modbus_uid: UNIT_ID, ..Default::default() };
        let client = tcp::Transport::new_with_cfg(MODBUS_SERVER_IP, cfg).expect("Failed to connect");
        Self { client }
    }
    
    fn read_coils(&mut self, address: u16, count: u16) -> Vec<bool> {
        self.client.read_coils(address, count).expect("read_coils failed")
            .into_iter().map(|c| c == Coil::On).collect()
    }
    
    fn write_coil(&mut self, address: u16, value: bool) {
        let coil = if value { Coil::On } else { Coil::Off };
        self.client.write_single_coil(address, coil).expect("write_coil failed");
    }
    
    fn read_holding_register(&mut self, address: u16) -> i32 {
        let regs = self.client.read_holding_registers(address, 1).expect("read_holding_register failed");
        regs[0] as i32
    }
    
    fn write_register(&mut self, address: u16, value: i32) {
        self.client.write_single_register(address, value as u16).expect("write_register failed");
    }
}

struct PlcProgram {
    client: ModbusClient,
}

impl PlcProgram {
    fn new() -> Self {
        Self { client: ModbusClient::new() }
    }
    
    fn run(&mut self) {
        let mut open_button: bool = false;
        let mut close_button: bool = false;
        let mut open_limit: bool = false;
        let mut closed_limit: bool = false;
        let mut obstacle_sensor: bool = false;
        let mut door_motor_open: bool = false;
        let mut door_motor_close: bool = false;
        let mut state: i32 = 0;
        let mut r_trig0_prev: bool = false;
        let mut r_trig0_q: bool = false;
        let mut _tmp_and5_out: bool = false;
        
        loop {
            open_button = self.client.read_coils(64, 1)[0];
            close_button = self.client.read_coils(65, 1)[0];
            open_limit = self.client.read_coils(66, 1)[0];
            closed_limit = self.client.read_coils(67, 1)[0];
            obstacle_sensor = self.client.read_coils(68, 1)[0];
            
            r_trig0_q = open_button && !r_trig0_prev; r_trig0_prev = open_button;
            if r_trig0_q {
                state = 1;
            } else if close_button {
                state = 2;
            }
            if state == 1 {
                if open_limit {
                    state = 0;
                }
                door_motor_open = true;
                door_motor_close = false;
            } else if state == 2 {
                if closed_limit {
                    state = 0;
                }
                door_motor_close = true;
                door_motor_open = false;
            } else if state == 0 {
                door_motor_open = false;
                door_motor_close = false;
            }
            if obstacle_sensor {
                state = 1;
            }
            
            self.client.write_coil(64, door_motor_open);
            self.client.write_coil(65, door_motor_close);
            
            std::thread::sleep(std::time::Duration::from_millis(20));
        }
    }
}

fn main() {
    let mut program = PlcProgram::new();
    program.run();
}