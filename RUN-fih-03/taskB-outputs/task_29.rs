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
        let mut rpm_set: i32 = 0;
        let mut digital_display: bool = false;
        let mut start_button: bool = false;
        let mut stop_button: bool = false;
        let mut conveyor_run: bool = false;
        let mut vision_sensor: i32 = 0;
        let mut start_light: bool = false;
        let mut display_box_counter: i32 = 0;
        
        loop {
            rpm_set = self.client.read_holding_register(30);
            start_button = self.client.read_coils(0, 1)[0];
            stop_button = self.client.read_coils(1, 1)[0];
            vision_sensor = self.client.read_holding_register(31);
            
            display_box_counter = vision_sensor;
            start_light = start_button;
            if stop_button {
                conveyor_run = false;
            } else if start_button {
                conveyor_run = true;
            }
            digital_display = conveyor_run;
            
            self.client.write_register(31, digital_display);
            self.client.write_register(30, conveyor_run);
            self.client.write_coil(0, start_light);
            self.client.write_register(32, display_box_counter);
            
            std::thread::sleep(std::time::Duration::from_millis(20));
        }
    }
}

fn main() {
    let mut program = PlcProgram::new();
    program.run();
}