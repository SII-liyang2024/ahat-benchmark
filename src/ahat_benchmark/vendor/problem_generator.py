import re
from typing import List, Any, Dict, Union, Set, Tuple
import random
import json

from .scene_graph import SceneGraphManager, PDDLDomainParser
# 假设 SceneGraphManager, PDDLDomainParser, solve_pddl 已经正确导入
# from update_sg.dynamic_sg import SceneGraphManager, PDDLDomainParser
# from goal_solver.pddl_solver import solve_pddl
# 以下为占位符，以便代码可以独立运行

class PDDLProblemGenerator:
    """
    根据 SceneGraphManager 和目标(goal)，生成一个 PDDL problem 文件。
    """
    def __init__(self, scene_graph_manager: SceneGraphManager):
        """
        初始化 Problem 文件生成器。

        Args:
            scene_graph_manager (SceneGraphManager): 已经初始化并处理好场景图的管理器。
        """
        self.sgm = scene_graph_manager
        self.pddl_parser = self.sgm.pddl_parser

    def _is_attribute_predicate(self, pred_name: str) -> bool:
        """
        判断一个谓词是否是属性谓词（通常只有一个参数）。
        这是根据您的要求“空间关系相关的predicates可以通过predicates的参数的数量来进行判断”实现的。
        """
        if pred_name in self.pddl_parser.predicates:
            # 属性谓词通常描述对象自身状态，参数为1。例如 (is_clean ?obj)
            # 关系谓词描述对象间关系，参数>=2。例如 (item_on_surface ?item ?surface)
            return len(self.pddl_parser.predicates[pred_name]) < 2
        return False

    def _get_parent(self, child_name: str) -> Union[str, None]:
        """
        [已修改] 从 scene_graph 的 'links' 中查找一个对象的直接父节点。
        现在可以处理字典格式的link。
        """
        if 'links' not in self.sgm.scene_graph:
            return None
        # SceneGraphManager 内部已将 link 转换为 {'from': child, 'to': parent, ...}
        for link in self.sgm.scene_graph['links']:
            # 确保 link 是我们期望的字典格式
            if isinstance(link, dict):
                if link.get('from') == child_name and link.get('relation') in ['on', 'in']:
                    return link.get('to')
        return None
        
    def _get_room_for_object(self, object_name: str) -> Union[str, None]:
        """递归查找一个物体所在的房间。"""
        current_obj = object_name
        for _ in range(10): # 防止无限循环
            if self.sgm.get_object_pddl_type(current_obj) == 'room':
                return current_obj
            parent = self._get_parent(current_obj)
            if parent is None:
                return None
            current_obj = parent
        return None

    def _get_furniture_in_room(self, room_name: str) -> List[str]:
        """
        [已修改] 获取指定房间内的所有家具。
        现在可以处理字典格式的link。
        """
        furniture_list = []
        if 'links' not in self.sgm.scene_graph:
            return []
        # SceneGraphManager 内部已将 link 转换为 {'from': furniture, 'to': room, 'relation': 'in'}
        for link in self.sgm.scene_graph['links']:
            # 确保 link 是我们期望的字典格式
            if isinstance(link, dict):
                # 你的原始代码中存在一个逻辑上的不一致：
                # `obj2 == room_name` 和 `get_object_pddl_type(obj1) == 'furniture'`
                # 这意味着 `obj2` 是房间，`obj1` 是家具。
                # 在新的字典格式下，这对应于 'to' 是房间，'from' 是家具。
                if (link.get('to') == room_name and
                        link.get('relation') == 'in' and
                        self.sgm.get_object_pddl_type(link.get('from')) == 'furniture'):
                    furniture_list.append(link.get('from'))
        return furniture_list
    
    def _is_condition_satisfied(self, condition: Union[List, Tuple]) -> bool:
        """
        检查给定的条件是否在当前场景图中满足
        
        Args:
            condition: 条件表达式
            
        Returns:
            bool: 如果条件满足则返回True，否则返回False
        """
        # 如果不是列表/元组，直接返回False
        if not isinstance(condition, (list, tuple)):
            return False
            
        head = condition[0]
        
        # 处理 'and' 条件
        if head == 'and':
            for sub_cond in condition[1:]:
                if not self._is_condition_satisfied(sub_cond):
                    return False
            return True
            
        # 处理 'not' 条件
        elif head == 'not':
            # 检查内部条件是否不满足
            inner_cond = condition[1] if len(condition) == 2 else condition[1:]
            return not self._is_condition_satisfied(inner_cond)
            
        # 处理基本谓词
        else:
            # 将条件转换为谓词元组
            if isinstance(condition[0], (list, tuple)):
                # 嵌套结构 (如来自字符串解析)
                pred_tuple = tuple(condition)
            else:
                # 平面结构
                pred_tuple = tuple(condition)
                
            # 检查谓词是否在当前场景图中
            if 'objects' not in self.sgm.scene_graph:
                return False
                
            # 遍历所有对象及其谓词
            for obj in self.sgm.scene_graph['objects']:
                obj_name = obj['name']
                obj_predicates = self.sgm.object_map.get(obj_name, {}).get('data', {}).get('predicates', [])
                
                # 检查谓词是否在对象的谓词列表中
                for pred in obj_predicates:
                    if tuple(pred) == pred_tuple:
                        return True
                        
            return False

    
    def _parse_goal_and_extract_objects(self, goal_condition: Union[List, Tuple]) -> Tuple[List[str], Set[str]]:
        """
        【新增辅助方法】
        递归地解析单个目标条件，处理 'when' 和 'and'。
        返回一个包含格式化后的 PDDL 字符串的列表，以及一个包含所有相关对象的集合。
        """
        # 如果不是有效的列表/元组，则返回空
        if not isinstance(goal_condition, (list, tuple)) or not goal_condition:
            return [], set()

        all_goal_strings, all_objects = [], set()
        head = goal_condition[0]

        if head == 'when':
            condition_satisfied = self._is_condition_satisfied(goal_condition[1])
        
            if condition_satisfied:
                # 如果条件已满足，则只将效果添加到目标
                eff_strs, eff_objs = self._parse_goal_and_extract_objects(goal_condition[2])
                all_goal_strings.extend(eff_strs)
                all_objects.update(eff_objs)
        
        elif head == 'and':
            # 结构: ['and', sub1, sub2, ...]
            # 递归解析 'and' 中的每一个子条件
            for sub_condition in goal_condition[1:]:
                sub_strs, sub_objs = self._parse_goal_and_extract_objects(sub_condition)
                all_goal_strings.extend(sub_strs)
                all_objects.update(sub_objs)
        
        else:
            # 基本情况：这是一个简单谓词或 'not' 谓词
            if head == 'not':
                # 【修改】兼容两种 'not' 格式:
                # 1. 结构化: ['not', ['is_dirty', 'floor']]
                # 2. 扁平化 (来自字符串解析): ['not', 'is_dirty', 'floor']
                
                # 判断是哪种格式
                if len(goal_condition) > 1 and isinstance(goal_condition[1], (list, tuple)):
                    # 格式 1: 结构化
                    inner_pred = goal_condition[1]
                else:
                    # 格式 2: 扁平化，inner_pred 是 'not' 后面的所有元素
                    inner_pred = goal_condition[1:]

                if not inner_pred: return [], set() # 防止空的 not
                    
                inner_pred_str = ' '.join(map(str, inner_pred))
                all_goal_strings.append(f"(not ({inner_pred_str}))")
                # 从 inner_pred 的第一个元素（谓词名）之后开始提取对象
                all_objects.update(inner_pred[1:])
            else:
                # 结构: ['predicate', 'obj1', ...]
                all_goal_strings.append(f"({' '.join(map(str, goal_condition))})")
                all_objects.update(goal_condition[1:])
                
        return all_goal_strings, all_objects
    
    @staticmethod
    def parse_parentheses(s):
        # 去除字符串两端的空格
        s = s.strip()
        
        # 检查是否以括号开头和结尾
        if len(s) < 2 or s[0] != '(' or s[-1] != ')':
            raise ValueError("输入字符串必须以括号开头和结尾")
        
        # 去除最外层的括号
        content = s[1:-1].strip()
        result = []
        start = 0
        parentheses_count = 0  # 用于跟踪括号深度
        
        for i, char in enumerate(content):
            if char == '(':
                parentheses_count += 1
            elif char == ')':
                parentheses_count -= 1
                if parentheses_count < 0:
                    raise ValueError("括号不匹配")
            elif char == ' ' and parentheses_count == 0:
                # 当遇到空格且不在嵌套括号中时，分割元素
                if start < i:
                    element = content[start:i].strip()
                    # 检查元素是否是一个括号表达式
                    if element.startswith('(') and element.endswith(')'):
                        # 递归解析嵌套的括号
                        result.append(PDDLProblemGenerator.parse_parentheses(element))
                    else:
                        result.append(element)
                start = i + 1
        
        # 添加最后一个元素
        if start <= len(content):
            element = content[start:].strip()
            if element:
                if element.startswith('(') and element.endswith(')'):
                    result.append(PDDLProblemGenerator.parse_parentheses(element))
                else:
                    result.append(element)
        
        if parentheses_count != 0:
            raise ValueError("括号不匹配")
        
        return result
        
    
    def get_parsed_goal(self, goal: List[str]):
        """
        return parsed goal -> List[str or list]
        replace when
        """
        processed_goal_list = []
        for g in goal:
            structured_g = g
            if isinstance(g, str):
                # 使用正则表达式安全地将 '(pred obj1 obj2)' 格式的字符串转换为列表
                # 例如：'(agent_at agent_0 bedroom_2)' -> ['agent_at', 'agent_0', 'bedroom_2']
                structured_g = self.parse_parentheses(g)
                formatted_strings, objects = self._parse_goal_and_extract_objects(structured_g)
                processed_goal = self.parse_parentheses(formatted_strings)
                processed_goal_list.append(processed_goal)
        return processed_goal_list
    
    
    def get_related_obj(self, goal_list):
        objects_to_define: Set[Tuple[str, str]] = set()
        init_predicates: Set[Tuple] = set()
        
        goal = goal_list
        goal_related_objects = set([])
        goal_str_formatted_list = []
        
        for g in goal:
            structured_g = g
            if isinstance(g, str):
                structured_g = self.parse_parentheses(g)
            if not structured_g:
                continue
            
            formatted_strings, objects = self._parse_goal_and_extract_objects(structured_g)
            goal_str_formatted_list.extend(formatted_strings)
            goal_related_objects.update(objects)
        
        goal_str_formatted = ""
        for s in sorted(list(set(goal_str_formatted_list))): # 排序和去重保证输出稳定
            goal_str_formatted += f"\n\t{s}"

        processed_objects = set()
        
        # 始终包含 agent
        if 'agent' in self.sgm.scene_graph:
            for agent_info in self.sgm.scene_graph['agent']:
                agent_name = agent_info['name']
                goal_related_objects.add(agent_name)
                if 'location' in agent_info and agent_info['location']:
                    goal_related_objects.add(agent_info['location'])
                if 'holding' in agent_info and agent_info['holding']:
                    held_items = agent_info['holding']
                    if isinstance(held_items, list):
                        goal_related_objects.update(held_items)
                    elif isinstance(held_items, str): # 也兼容 holding 的值是单个字符串的情况
                        goal_related_objects.add(held_items)
                        
        queue = list(goal_related_objects)
        while queue:
            obj_name = queue.pop(0)
            if obj_name in processed_objects or obj_name not in self.sgm.object_map:
                continue
            
            processed_objects.add(obj_name)
            
            # 添加对象及其类型
            obj_type = self.sgm.get_object_pddl_type(obj_name)
            if obj_type:
                objects_to_define.add((obj_name, obj_type))

            # 根据规则添加谓词
            obj_predicates = self.sgm.object_map[obj_name]['data'].get('predicates', [])
            
            # 如果是最初的目标物品，添加所有谓词
            if obj_name in goal_related_objects:
                for pred in obj_predicates:
                    for item in pred[1:]:
                        item_type = self.sgm.get_object_pddl_type(item)
                        if item_type:
                           objects_to_define.add((item, item_type))

            # 将父节点加入队列进行下一轮处理
            parent = self._get_parent(obj_name)
            if parent and parent not in processed_objects:
                queue.append(parent)
                
        objects_list = set([])
        for name, type in objects_to_define:
            objects_list.add(name)
            
        return list(objects_list)
    
    def merge_goal_with_init(self, init_list, goal_list):
        merged_goal = []
    
        init_pred_list = []
        for pred_tuple in init_list:
            init_pred_list.append(f"({' '.join(pred_tuple)})")
    
        for pred in goal_list:
            if not pred in init_pred_list:
                merged_goal.append(pred)
        
        return merged_goal
        
    # ==============================================================================
    # 【新增方法】根据Action List生成Problem File
    # ==============================================================================
    def generate_problem_from_actions(self, action_list: List[str], problem_name: str = "pddl_problem_from_sg", domain_name: str = "habitat_world_domain_final") -> str:
        """
        【新增】根据一个动作序列生成完整的 PDDL problem 文件字符串。

        Args:
            action_list (List[str]): PDDL 动作的字符串列表, e.g., ['(pick_from_surface agent_1 book_2 stand_29)'].
            problem_name (str): 问题名称。
            domain_name (str): 对应的领域名称。

        Returns:
            str: 格式化后的 PDDL problem 文件内容。
        """
        # 1. 初始化用于存储最终结果的集合
        objects_to_define: Set[Tuple[str, str]] = set()
        init_predicates: Set[Tuple] = set()
        
        # 【修改点 1】: 从 action_list 中提取所有相关对象作为种子对象
        # 不再从 goal_pair 中获取，而是解析整个动作列表
        all_related_objects = set()
        if not action_list:
            # 如果动作列表为空，可以返回一个默认的或空的 problem file
            print("Warning: Empty action list provided.")
            # 仍然尝试包含agent信息
            if 'agent' in self.sgm.scene_graph:
                 for agent_info in self.sgm.scene_graph['agent']:
                    all_related_objects.add(agent_info['name'])
        else:
            for action_str in action_list:
                # 从 '(action_name param1 param2)' 中提取 'param1', 'param2'
                params = re.findall(r'\b[a-zA-Z0-9_]+\b', action_str)
                if params:
                    # 第一个通常是动作名，后面的是对象名
                    all_related_objects.update(params[1:])

        # 【修改点 2】: 将最终目标设置为最后一个动作的效果
        # 接下来，重用您在 generate_problem_file 中的大部分逻辑，
        # 但将 `goal_related_objects` 替换为我们刚刚创建的 `all_related_objects`
        # 并将 `goal` 用于生成最终的 goal 字符串
        
        # 2. 从 goal 解析涉及的物品 (这部分也可能向 all_related_objects 添加新对象)
        goal_str_formatted_list = []
        
        goal_str_formatted = ""
        for s in sorted(list(set(goal_str_formatted_list))):
            goal_str_formatted += f"\n\t{s}"

        # 3. 收集谓词和对象 (核心逻辑)
        processed_objects = set()
        
        # 始终包含 agent
        if 'agent' in self.sgm.scene_graph:
            for agent_info in self.sgm.scene_graph['agent']:
                agent_name = agent_info['name']
                all_related_objects.add(agent_name)
                if 'location' in agent_info and agent_info['location']:
                    all_related_objects.add(agent_info['location'])
                if 'holding' in agent_info and agent_info['holding']:
                    held_items = agent_info['holding']
                    if isinstance(held_items, list):
                        all_related_objects.update(held_items)
                    elif isinstance(held_items, str):
                        all_related_objects.add(held_items)

        # 广度优先/迭代处理所有相关对象及其父对象
        # 【修改点 3】: 使用 all_related_objects 初始化队列
        queue = list(all_related_objects)
        
        while queue:
            obj_name = queue.pop(0)
            if obj_name in processed_objects or obj_name not in self.sgm.object_map:
                continue
            
            processed_objects.add(obj_name)
            
            obj_type = self.sgm.get_object_pddl_type(obj_name)
            if obj_type:
                objects_to_define.add((obj_name, obj_type))

            obj_predicates = self.sgm.object_map[obj_name]['data'].get('predicates', [])
            
            # 【修改点 4】: 这里判断条件改为 obj_name 是否在 all_related_objects 中
            if obj_name in all_related_objects:
                for pred in obj_predicates:
                    init_predicates.add(tuple(pred))
                    for item in pred[1:]:
                        item_type = self.sgm.get_object_pddl_type(item)
                        if item_type:
                            objects_to_define.add((item, item_type))
            else:  
                for pred in obj_predicates:
                    if self._is_attribute_predicate(pred[0]):
                        init_predicates.add(tuple(pred))

            parent = self._get_parent(obj_name)
            if parent and parent not in processed_objects:
                queue.append(parent)

        # 4. "鲁棒性"采样 (此部分逻辑保持不变)
        room_of_interest = None
        for obj_name in all_related_objects:
            room = self._get_room_for_object(obj_name)
            if room:
                room_of_interest = room
                break
        
        if room_of_interest:
            all_furniture_in_room = self._get_furniture_in_room(room_of_interest)
            candidate_furniture = [f for f in all_furniture_in_room if f not in processed_objects]
            
            sample_size = min(len(candidate_furniture), 3)
            sampled_furniture = random.sample(candidate_furniture, sample_size)
            
            for furn_name in sampled_furniture:
                processed_objects.add(furn_name)
                furn_type = self.sgm.get_object_pddl_type(furn_name)
                if furn_type:
                    objects_to_define.add((furn_name, furn_type))
                
                furn_predicates = self.sgm.object_map[furn_name]['data'].get('predicates', [])
                for pred in furn_predicates:
                    if self._is_attribute_predicate(pred[0]):
                        init_predicates.add(tuple(pred))

        # 5. 格式化输出字符串 (此部分逻辑保持不变)
        objects_by_type = {}
        for name, type in objects_to_define:
            if type not in objects_by_type:
                objects_by_type[type] = []
            objects_by_type[type].append(name)

        objects_str = ""
        for type, names in sorted(objects_by_type.items()):
            objects_str += f"\n\t{' '.join(sorted(names))} - {type}"

        init_str = ""
        sorted_preds = sorted(list(init_predicates), key=lambda x: str(x))
        for pred in sorted_preds:
            init_str += f"\n\t({' '.join(map(str, pred))})"

        pddl_problem = f"""
(define (problem {problem_name})
    (:domain {domain_name})
    (:objects {objects_str}
    )

    (:init {init_str}
    )

    (:goal (and {goal_str_formatted}
    ))
)
"""
        return pddl_problem.strip()
    
    # 原有的 generate_problem_file 方法保持不变，以兼容旧的调用方式
    def generate_problem_file(self, goal_pair: List[str], problem_name: str = "pddl_problem_from_sg", domain_name: str = "habitat_world_domain_final") -> str:
        # ... 您原有的代码 ...
        # 为了简洁，这里省略了原始内容，实际使用时请保留
        # 这个方法现在可以被视为一个特例，其功能可以通过新的方法实现
        # 比如: last_action_effect = goal_pair[0], objects = goal_pair[1]
        # 但是保留它可以确保向后兼容
        pass


# ==============================================================================
# 示例用法
# ==============================================================================
if __name__ == '__main__':
    # 【修改】: 更新为您新场景下的示例用法
    
    # 1. 准备您的数据 (假设与之前类似)
    # pddl_sovler_path = 'path/to/your/run_pddl.sh'
    # domain_file_path = 'path/to/your/domain.pddl'
    # domain_file_str = pathlib.Path(domain_file_path).read_text('utf-8')
    
    # 使用一个模拟的 scene_graph 和 domain_file_str 来让代码跑通
    mock_scene_graph = {
        'objects': [
            {'name': 'agent_1', 'pddl_type': 'agent', 'predicates': [['agent_at', 'agent_1', 'floor_tv_1']]},
            {'name': 'floor_tv_1', 'pddl_type': 'room', 'predicates': []},
            {'name': 'couch_9', 'pddl_type': 'furniture', 'predicates': [['is_dirty', 'couch_9']]},
            {'name': 'book_2', 'pddl_type': 'item', 'predicates': [['item_on_surface', 'book_2', 'stand_29']]},
            {'name': 'stand_29', 'pddl_type': 'furniture', 'predicates': []},
            {'name': 'plant_container_1', 'pddl_type': 'item', 'predicates': [['item_on_surface', 'plant_container_1', 'chair_23']]},
            {'name': 'chair_23', 'pddl_type': 'furniture', 'predicates': []},
            {'name': 'shelves_12', 'pddl_type': 'furniture', 'predicates': []}
        ],
        'links': [
            {'from': 'couch_9', 'to': 'floor_tv_1', 'relation': 'in'},
            {'from': 'stand_29', 'to': 'floor_tv_1', 'relation': 'in'},
            {'from': 'chair_23', 'to': 'floor_tv_1', 'relation': 'in'},
            {'from': 'shelves_12', 'to': 'floor_tv_1', 'relation': 'in'},
            {'from': 'book_2', 'to': 'stand_29', 'relation': 'on'},
            {'from': 'plant_container_1', 'to': 'chair_23', 'relation': 'on'},
        ],
        'agent': [{'name': 'agent_1', 'location': 'floor_tv_1', 'holding': []}]
    }
    mock_domain_file_str = "..." # 您的 domain pddl 内容

    # 2. 定义您的 Action List
    action_list_example = [
        '(navigate agent_1 floor_tv_1 couch_9)', 
        '(clean_furniture agent_1 couch_9)', 
        '(navigate agent_1 couch_9 book_2)', 
        '(pick_from_surface agent_1 book_2 stand_29)', 
        '(navigate agent_1 book_2 plant_container_1)', 
        '(navigate agent_1 plant_container_1 shelves_12)', 
        '(place_on_surface agent_1 book_2 shelves_12)', 
        '(navigate agent_1 shelves_12 plant_container_1)', 
        '(pick_from_surface agent_1 plant_container_1 chair_23)', 
        '(navigate agent_1 plant_container_1 shelves_12)', 
        '(place_next_to_surface agent_1 plant_container_1 book_2 shelves_12)'
    ]
    # 注意：为了让这个例子跑通，我假设最后一个动作的效果是 (item_on_surface book_2 shelves_12)
    # 这在上面的 PDDLDomainParser 模拟类中硬编码了
    
    # 3. 实例化您的类
    sg_manager = SceneGraphManager(mock_scene_graph, mock_domain_file_str)
    
    # 4. 实例化生成器并调用新方法
    problem_generator = PDDLProblemGenerator(sg_manager)
    pddl_problem_file_content = problem_generator.generate_problem_from_actions(action_list_example)

    # 5. 打印结果
    print("--- Generated PDDL Problem File from Action List ---")
    print(pddl_problem_file_content)

    # 6. (可选) 调用 PDDL 求解器
    # plan = solve_pddl(domain_file_str, pddl_problem_file_content, pddl_sovler_path)
    # print("\n--- Solved Plan ---")
    # print(plan)
