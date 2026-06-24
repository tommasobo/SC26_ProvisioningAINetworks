import unittest
from pathlib import Path
from dep_graph_generator import DependencyGraphGenerator
from lp_converter import LPConverter
from lp_analyzer import LPAnalyzer
from topology import NetTopology


class TestGraphAnalysis(unittest.TestCase):
    DATA = Path(__file__).resolve().parent / "data"

    def test_net_lat_sen_blocking(self) -> None:
        """
        Tests the network latency sensitivity metric from
        the dependency graph generated from the goal file of a
        simple blocking MPI program.
        1 (l2) -> 0 (l1) -> 2 (l3) : Rank 0
        [1000]      |[1500]  [2000]
                    | 
                    | L + (4 - 1) * 6
                    |
                    V
        4 (l2) -> 3 (l1) -> 5 (l3) : Rank 1
        [3000]      [1500]  [2000]
        """
        goal_path = self.DATA / "blocking.goal"
        generator = DependencyGraphGenerator(str(goal_path))
        dep_graph = generator.generate()
        topology = NetTopology.default_topology(dep_graph.num_ranks)
        lp_model = LPConverter(dep_graph).convert_to_lp(topology=topology)
        analyzer = LPAnalyzer()
        net_lat_sen = analyzer.get_net_lat_sensitivity(lp_model)
        self.assertEqual(len(net_lat_sen.critical_latencies), 3)
        self.assertEqual(tuple(net_lat_sen.critical_latencies[0]), (0, 0.0))
        self.assertAlmostEqual(net_lat_sen.critical_latencies[1][0], 499.928, places=3)
        self.assertEqual(net_lat_sen.critical_latencies[1][1], 1.0)
        self.assertEqual(tuple(net_lat_sen.critical_latencies[2]), (1000000000, 1.0))

    def test_net_lat_sen_non_blocking(self) -> None:
        """
        Tests the network latency sensitivity metric from
        the dependency graph generated from the goal file of a
        simple blocking MPI program.
            ---> 2 (l3) ------
           /     [2000]      |
          /                  V
        1 (l2) -> 0 (l1) -> 3 (l4) : Rank 0
        [1000]      |[1500]  [4000]
                    | 
                    | L + (4 - 1) * 6
                    |
                    V
        5 (l2) -> 4 (l1) -> 6 (l3)  : Rank 1
        [3000]      [1500]  [2000]
        """
        goal_path = self.DATA / "non_blocking.goal"
        generator = DependencyGraphGenerator(str(goal_path))
        dep_graph = generator.generate()
        topology = NetTopology.default_topology(dep_graph.num_ranks)
        lp_model = LPConverter(dep_graph).convert_to_lp(topology=topology)
        analyzer = LPAnalyzer()
        net_lat_sen = analyzer.get_net_lat_sensitivity(lp_model)
        self.assertEqual(len(net_lat_sen.critical_latencies), 3)
        self.assertEqual(tuple(net_lat_sen.critical_latencies[0]), (0, 0))
        self.assertAlmostEqual(net_lat_sen.critical_latencies[1][0], 999.928, places=3)
        self.assertEqual(net_lat_sen.critical_latencies[1][1], 1.0)
        self.assertEqual(tuple(net_lat_sen.critical_latencies[2]), (1000000000, 1.0))

if __name__ == "__main__":
    unittest.main()
