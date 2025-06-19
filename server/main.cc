#include <chrono>
#include <cstdio>
#include <fstream>
#include <iomanip>
#include <map>
#include <sstream>
#include <string>
#include <unordered_map>

#include "json.hpp"

using json = nlohmann::json;

double double_to_fixed(double value) {
  std::ostringstream ss;
  ss << std::fixed << std::setprecision(2) << value;
  return std::stod(ss.str());
}

int main() {
  std::string home_dir = getenv("HOME");
  std::string output_path = home_dir + "/memory_usage.json";

  json memory_data;

  auto now = std::chrono::system_clock::now();
  std::time_t now_c = std::chrono::system_clock::to_time_t(now);
  std::stringstream time_ss;
  time_ss << std::put_time(std::localtime(&now_c), "%Y-%m-%d %H:%M:%S");
  memory_data["time"] = time_ss.str();

  std::unordered_map<std::string, double> mems;
  std::ifstream ifs("/proc/meminfo");
  std::string line;
  bool found_total = false;
  bool found_available = false;
  while (!(found_total && found_available) && std::getline(ifs, line)) {
    std::stringstream ss(line);
    std::string name;
    long long value;
    ss >> name >> value;
    if (name == "MemTotal:") {
      memory_data["total_memory"] = double_to_fixed(value / 1024. / 1024.);
      found_total = true;
    } else if (name == "MemAvailable:") {
      memory_data["available_memory"] = double_to_fixed(value / 1024. / 1024.);
      found_available = true;
    }
  }
  ifs.close();

  memory_data["used_memory"] =
      double_to_fixed(memory_data["total_memory"].get<double>() -
                      memory_data["available_memory"].get<double>());

  FILE *pipe = popen(
      "docker stats --no-stream --format \"{{.Name}} {{.MemUsage}}\"", "r");
  if (pipe) {
    char buffer[256];
    while (fgets(buffer, sizeof(buffer), pipe) != NULL) {
      std::stringstream ss(buffer);
      std::string name;
      std::string value;
      ss >> name >> value;
      std::string unit = value.substr(value.size() - 3);

      double mem_value = 0.0;
      if (unit == "GiB") {
        mem_value = std::stod(value.substr(0, value.size() - 3));
      } else if (unit == "MiB") {
        mem_value = std::stod(value.substr(0, value.size() - 3)) / 1024.0;
      } else if (unit == "KiB") {
        mem_value =
            std::stod(value.substr(0, value.size() - 3)) / 1024.0 / 1024.0;
      }

      memory_data[name] = double_to_fixed(mem_value);
    }
    pclose(pipe);
  }

  std::ofstream outfile(output_path);
  if (outfile) {
    outfile << memory_data.dump(4) << std::endl;
    outfile.close();
  } else {
    return 1;
  }
}
