import re
from typing import List, Dict, Any, Union
import json
import pathlib
from typing import List, Any, Dict, Union, Set, Tuple
import copy


class PDDLDomainParser:
    """
    一个用于解析PDDL领域文件的类。
    它可以提取类型、谓词和动作，包括它们的参数、前置条件和效果。
    """

    def __init__(self, domain_content: str):
        """
        初始化解析器。

        Args:
            domain_content (str): PDDL领域文件的完整字符串内容。
        """
        self.content = self._preprocess_content(domain_content)
        self.tokens = self.content.split()
        # 解析S-表达式，这是PDDL的基础结构
        self.parsed_structure = self._s_exp_parse(self.tokens)
        
        # 从解析后的结构中提取具体信息
        self.types = self._extract_types()
        self.predicates = self._extract_predicates()
        self.actions = self._extract_actions()

    def _preprocess_content(self, content: str) -> str:
        """预处理文本，移除注释并标准化括号，方便解析。"""
        content = re.sub(r';.*', '', content)  # 移除注释
        content = content.lower() # 转换为小写以实现不区分大小写的匹配
        content = content.replace('(', ' ( ').replace(')', ' ) ')
        return content

    def _s_exp_parse(self, tokens: List[str]) -> List[Any]:
        """
        将token列表解析为S-表达式（嵌套列表）。
        """
        if not tokens:
            raise ValueError("s_exp_parse: Unexpected end of input")
        token = tokens.pop(0)
        if token == '(':
            exp = []
            while tokens and tokens[0] != ')':
                exp.append(self._s_exp_parse(tokens))
            if not tokens:
                raise ValueError("s_exp_parse: Missing ')'")
            tokens.pop(0)  # 弹出 ')'
            return exp
        elif token == ')':
            raise ValueError("s_exp_parse: Unexpected ')'")
        else:
            return token

    def _find_section(self, section_name: str) -> List[Any]:
        """在解析后的结构中查找指定的部分，例如 ':predicates' 或 ':action'。"""
        for element in self.parsed_structure:
            if isinstance(element, list) and element and element[0] == section_name:
                return element
        return []

    def _extract_types(self) -> Dict[str, str]:
        """提取类型及其继承关系。"""
        types_dict = {'object': None} # 'object' 是PDDL中的根类型
        types_section = self._find_section(':types')
        if not types_section:
            return types_dict
        
        # 格式: [physobj, -, location, room, -, physobj, ...]
        type_list = types_section[1:]
        current_types = []
        for item in type_list:
            if item == '-':
                parent_type = type_list[type_list.index(item) + 1]
                for t in current_types:
                    types_dict[t] = parent_type
                current_types = []
            else:
                if item not in types_dict:
                     types_dict[item] = 'object' # 默认父类型
                current_types.append(item)
        return types_dict


    def _parse_typed_list(self, typed_list: List[str]) -> Dict[str, str]:
        """解析带有类型的列表，例如 '(?ag - agent ?obj - physobj)'。"""
        params = {}
        i = 0
        while i < len(typed_list):
            param_name = typed_list[i]
            if i + 1 < len(typed_list) and typed_list[i+1] == '-':
                param_type = typed_list[i+2]
                params[param_name] = param_type
                i += 3
            else:
                # 处理没有明确类型的参数，默认为 'object'
                params[param_name] = 'object'
                i += 1
        return params

    def _extract_predicates(self) -> Dict[str, Dict[str, str]]:
        """提取所有谓词及其参数。"""
        predicates_map = {}
        predicates_section = self._find_section(':predicates')
        if not predicates_section:
            return predicates_map
        
        for pred_def in predicates_section[1:]:
            if isinstance(pred_def, list):
                pred_name = pred_def[0]
                params = self._parse_typed_list(pred_def[1:])
                predicates_map[pred_name] = params
        return predicates_map

    def _extract_actions(self) -> Dict[str, Dict[str, Any]]:
        """提取所有动作，包括参数、前置条件和效果。"""
        actions_map = {}
        for element in self.parsed_structure:
            if isinstance(element, list) and element and element[0] == ':action':
                action_name = element[1]
                action_info = {'name': action_name}
                
                # 查找 :parameters, :precondition, :effect
                for i in range(2, len(element), 2):
                    key = element[i]
                    value = element[i+1]
                    if key == ':parameters':
                        action_info['parameters'] = self._parse_typed_list(value)
                    elif key == ':precondition':
                        action_info['precondition'] = value
                    elif key == ':effect':
                        action_info['effect'] = value
                
                actions_map[action_name] = action_info
        return actions_map
    
    def get_action_effects(self, concrete_action: str) -> List[str]:
        """
        根据一个具体的、已实例化的动作，返回其效果列表。

        Args:
            concrete_action (str): 一个代表具体动作的字符串，
                                   例如 "(pick apple_1 robot_1 arm_1 room_1)"。

        Returns:
            List[str]: 一个字符串列表，表示该动作产生的效果。
                       例如 ["(not (at robot_1 room_1))", "(at-obj apple_1 room_1)"]。

        Raises:
            ValueError: 如果动作格式无效、动作名称不存在或参数数量不匹配。
        """
        # 1. 解析输入的具体动作字符串
        try:
            processed_str = self._preprocess_content(concrete_action)
            tokens = processed_str.split()
            # s_exp_parse会消耗tokens，所以无需担心后续使用
            parsed_action = self._s_exp_parse(tokens)
        except (ValueError, IndexError) as e:
            raise ValueError(f"无法解析动作字符串: '{concrete_action}'. 错误: {e}")

        if not isinstance(parsed_action, list) or len(parsed_action) < 1:
            raise ValueError(f"无效的动作格式: '{concrete_action}'")

        action_name = parsed_action[0]
        concrete_args = parsed_action[1:]

        # 2. 在已解析的动作中查找该动作的定义
        if action_name not in self.actions:
            raise ValueError(f"动作 '{action_name}' 在领域定义中未找到。")
        
        action_def = self.actions[action_name]
        
        # 3. 将形式参数映射到具体参数
        formal_params = list(action_def.get('parameters', {}).keys())
        if len(formal_params) != len(concrete_args):
            raise ValueError(
                f"动作 '{action_name}' 的参数数量不匹配。"
                f"需要 {len(formal_params)} 个，但提供了 {len(concrete_args)} 个。"
            )
        
        param_map = dict(zip(formal_params, concrete_args))

        # 4. 获取效果的S-表达式结构
        effect_structure = action_def.get('effect', [])
        
        # 效果通常在 '(and ...)' 结构中，我们需要处理这种情况
        if effect_structure and effect_structure[0] == 'and':
            # 获取 'and' 之后的所有独立效果表达式
            raw_effects = effect_structure[1:]
        else:
            # 处理没有 'and' 的单个效果或空效果的情况
            raw_effects = [effect_structure] if effect_structure else []

        # 5. 替换参数并格式化为最终的字符串列表
        final_effects = []
        for effect_exp in raw_effects:
            # 递归地替换表达式中的参数变量
            substituted_exp = self._substitute_expression(effect_exp, param_map)
            # 将替换后的表达式列表格式化回标准的PDDL字符串
            final_effects.append(self._format_expression_to_string(substituted_exp))
            
        return final_effects

    def _substitute_expression(self, expression: Any, param_map: Dict[str, str]) -> Any:
        """
        [辅助函数] 递归地替换S-表达式中的参数。
        例如，将 ['at', '?obj', '?loc'] 和 {'?obj': 'apple', '?loc': 'table'}
        转换为 ['at', 'apple', 'table']。
        """
        if not isinstance(expression, list):
            # 如果是原子（字符串），检查它是否为需要替换的参数
            return param_map.get(expression, expression)
        else:
            # 如果是列表，递归地对其中每个元素进行替换
            return [self._substitute_expression(item, param_map) for item in expression]

    def _format_expression_to_string(self, expression: Any) -> str:
        """
        [辅助函数] 递归地将S-表达式（嵌套列表）格式化为PDDL字符串。
        例如，将 ['not', ['at', 'robot', 'room1']] 转换为 "(not (at robot room1))"。
        """
        if not isinstance(expression, list):
            return str(expression)
        
        # 对列表中的每个元素递归格式化，然后用空格连接，并用括号包裹
        inner_content = ' '.join(self._format_expression_to_string(item) for item in expression)
        return f"({inner_content})"
    
    
class SceneGraphManager:
    """
    [新版本] 管理Scene Graph，并根据PDDL动作动态维护它。
    这个版本在初始化时会自动将list-based的links升级为dictionary-based，以支持复杂谓词。
    """
    def __init__(self, scene_graph: Dict[str, Any], domain_file_path_or_file: str):
        """
        [已修改] 初始化Scene Graph管理器。
        """
        if pathlib.Path(domain_file_path_or_file).exists():
            domain_content = pathlib.Path(domain_file_path_or_file).read_text(encoding='utf-8')
        else:
            domain_content = domain_file_path_or_file
        self.scene_graph = copy.deepcopy(scene_graph)
        self.pddl_parser = PDDLDomainParser(domain_content)
        
        # --- 核心修改：在初始化时，自动升级links的格式 ---
        self._upgrade_links_format()
        
        # 后续步骤与之前相同，但现在可以安全地处理字典格式的links
        self._build_object_map()
        self.extract_all_predicates()

    def _upgrade_links_format(self):
        """
        [新增] 检查并转换links格式。
        将输入的 ['container', 'item', 'relation'] 列表转换为
        {'relation': ..., 'from': ..., 'to': ...} 的字典格式，以便内部处理。
        这个操作是幂等的，如果已经是字典格式则不会重复转换。
        """
        if 'links' not in self.scene_graph or not isinstance(self.scene_graph['links'], list):
            self.scene_graph['links'] = []
            return

        upgraded_links = []
        for link in self.scene_graph['links']:
            # 如果是旧的列表格式 [obj1, obj2, relation]
            if isinstance(link, list) and len(link) == 3:
                obj1, obj2, relation = link
                new_link_dict = {}
                # 根据你的原始代码逻辑:
                # (item_on_surface ?obj ?surface) -> link: [surface, obj, 'on']
                # (item_in_receptacle ?obj ?receptacle) -> link: [receptacle, obj, 'in']
                # 所以 obj2 是 item, obj1 是 container/surface
                if relation in ['on', 'in']:
                    new_link_dict = {'relation': relation, 'from': obj2, 'to': obj1}
                # 你可以为其他简单的关系在这里添加转换规则
                
                if new_link_dict:
                    upgraded_links.append(new_link_dict)
            
            # 如果已经是新的字典格式，直接保留
            elif isinstance(link, dict):
                upgraded_links.append(link)
        
        # 用升级后的links列表替换旧的
        self.scene_graph['links'] = upgraded_links

    def _build_object_map(self):
        """创建一个从对象名称到其类别和详细信息的映射，并确保每个物体都有谓词列表。"""
        self.object_map = {}
        for category, items in self.scene_graph.items():
            if category == 'links':
                continue
            if isinstance(items, list):
                # 使用 enumerate 和索引来原地修改列表中的元素
                for i, item in enumerate(items):
                    if isinstance(item, str):
                        item_dict = {'name': item, 'predicates': []}
                        self.scene_graph[category][i] = item_dict # 原地替换
                        item = item_dict

                    if isinstance(item, dict):
                        if 'predicates' not in item:
                            item['predicates'] = []
                        if 'name' in item:
                            self.object_map[item['name']] = {'category': category, 'data': item}

    # ... get_object_pddl_type 方法保持不变 ...
    def get_object_pddl_type(self, object_name: str) -> Union[str, None]:
        if object_name not in self.object_map: return None
        category = self.object_map[object_name]['category']
        return category[:-1] if category.endswith('s') else category
    
    # ... extract_all_predicates 方法保持不变 (因为它依赖于已转换的字典格式) ...
    def extract_all_predicates(self) -> None:
        """
        从当前的Scene Graph中提取所有谓词，并将它们直接存储到相关的物体节点中。
        此方法现在可以解析新的基于字典的 `links` 格式。
        """
        # 1. 初始化/清空所有物体的谓词列表
        for obj_name in self.object_map:
            if 'predicates' in self.object_map[obj_name]['data']:
                self.object_map[obj_name]['data']['predicates'].clear()

        # 2. 从 "states" 中提取一元谓词
        for obj_name, obj_info in self.object_map.items():
            obj_data = obj_info['data']
            if 'states' in obj_data and obj_data['states'] is not None:
                for state_name, state_value in obj_data['states'].items():
                    if state_value and state_name in self.pddl_parser.predicates:
                        obj_data['predicates'].append([state_name, obj_name])

        # 3. [核心修改] 从 "links" 中提取关系谓词 (现在处理字典)
        if 'links' in self.scene_graph:
            for link in self.scene_graph['links']:
                if not isinstance(link, dict) or 'relation' not in link:
                    continue # 跳过格式不正确的link

                relation = link['relation']
                predicate = None
                
                # change relation from parents to child
                if relation == 'on' and 'from' in link and 'to' in link:
                    obj, surface = link['from'], link['to']
                    obj_type = self.get_object_pddl_type(obj)
                    surface_type = self.get_object_pddl_type(surface)
                    if obj_type not in ['agent', 'person'] and surface_type not in ['agent', 'person']:
                        predicate = ['item_on_surface', obj, surface]
                        if obj in self.object_map:
                            self.object_map[obj]['data']['predicates'].append(predicate)
                
                elif relation == 'in' and 'from' in link and 'to' in link:
                    obj, container = link['from'], link['to']
                    obj_type = self.get_object_pddl_type(obj)
                    container_type = self.get_object_pddl_type(container)
                    
                    if obj_type == 'furniture' and container_type == 'room':
                         predicate = ['furniture_in_room', obj, container]
                    elif obj_type == 'device' and container_type == 'room':
                         predicate = ['device_in_room', obj, container]
                    elif obj_type == 'agent' or obj_type == 'person':
                        continue
                    else:
                         predicate = ['item_in_receptacle', obj, container]

                    if obj in self.object_map:
                        self.object_map[obj]['data']['predicates'].append(predicate)

                # --- 新增对 next_to 的处理 ---
                elif relation == 'next_to' and 'obj1' in link and 'obj2' in link and 'location' in link:
                    i1, i2, s = link['obj1'], link['obj2'], link['location']
                    predicate = ['next_to', i1, i2, s]
                    # 将这个关系谓词存储在所有三个相关的对象上，以便查询
                    if i1 in self.object_map:
                         self.object_map[i1]['data']['predicates'].append(predicate)
                    if i2 in self.object_map:
                         self.object_map[i2]['data']['predicates'].append(predicate)
                    if s in self.object_map:
                         self.object_map[s]['data']['predicates'].append(predicate)
        
        # 4. 从 "agent" 中提取谓词
        if 'agent' in self.scene_graph:
            for agent_info in self.scene_graph['agent']:
                agent_name = agent_info['name']
                
                if 'holding' in agent_info and agent_info['holding'] is not None:
                    held_item = agent_info['holding']
                    self.object_map[agent_name]['data']['predicates'].append(['holding', agent_name, held_item])
                else:
                    self.object_map[agent_name]['data']['predicates'].append(['handempty', agent_name])

                if 'location' in agent_info:
                    location_name = agent_info['location']
                    if location_name in self.object_map:
                        self.object_map[location_name]['data']['predicates'].append(['agent_at', agent_name, location_name])

        if 'person' in self.scene_graph and self.scene_graph['person'] is not None:
            for person_info in self.scene_graph['person']:
                person_name = person_info['name']
                if 'loaction' in person_info:
                    location_name = person_info['location']
                    if location_name in self.object_map:
                        self.object_map[location_name]['data']['predicates'].append(['person_at', person_name, location_name])
                if 'p_holding' in person_info and person_info['p_holding'] is not None:
                    hold_item = person_info['p_holding']
                    self.object_map[person_name]['data']['predicates'].append(['p_holding', person_name, hold_item])
                
        # 5. 对每个物体的谓词列表进行去重
        for obj_name in self.object_map:
            preds = self.object_map[obj_name]['data']['predicates']
            if preds:
                unique_preds = [list(p) for p in set(tuple(p) for p in preds)]
                self.object_map[obj_name]['data']['predicates'] = unique_preds
        return

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
                        result.append(SceneGraphManager.parse_parentheses(element))
                    else:
                        result.append(element)
                start = i + 1
        
        # 添加最后一个元素 
        if start <= len(content):
            element = content[start:].strip()
            if element:
                if element.startswith('(') and element.endswith(')'):
                    result.append(SceneGraphManager.parse_parentheses(element))
                else:
                    result.append(element)
        
        if parentheses_count != 0:
            raise ValueError("括号不匹配")
        
        return result

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
            if 'objects' not in self.scene_graph:
                return False
                
            # 遍历所有对象及其谓词
            for obj in self.scene_graph['objects']:
                obj_name = obj['name']
                obj_predicates = self.object_map.get(obj_name, {}).get('data', {}).get('predicates', [])
                
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

    def parse_predicate(self, predicate_with_param: List[str]):
        """
        return parsed effect -> List[str or list]
        replace when
        """
        processed_goal_list = []
        structured_g = predicate_with_param
        if isinstance(predicate_with_param, str):
            # 使用正则表达式安全地将 '(pred obj1 obj2)' 格式的字符串转换为列表
            # 例如：'(agent_at agent_0 bedroom_2)' -> ['agent_at', 'agent_0', 'bedroom_2']
            structured_g = self.parse_parentheses(predicate_with_param)
        formatted_strings, objects = self._parse_goal_and_extract_objects(structured_g)
        for effect_string in formatted_strings:
            processed_goal = self.parse_parentheses(effect_string)
            processed_goal_list.append(processed_goal)
        return processed_goal_list

    @staticmethod
    def fill_predicate_with_params(predicate, param_map):
        if isinstance(predicate, list):
            for index, value in enumerate(predicate):
                if isinstance(value, list):
                    SceneGraphManager.fill_predicate_with_params(value, param_map)
                else: 
                    if value[0] == '?':
                        predicate[index] = param_map.get(value)
                        if param_map.get(value) == None:
                            raise ValueError(f"can not get params {value} from param map")
            return predicate
            

    # ... apply_action 和 _apply_effect 方法保持不变 (因为它们产生并依赖字典格式) ...
    def apply_action(self, action_name: str, bound_params: List[str]):
        """
        将一个已绑定的PDDL动作应用到Scene Graph上，修改其状态。
        """
        if action_name not in self.pddl_parser.actions:
            raise ValueError(f"动作 '{action_name}' 在PDDL领域中未定义。")

        action = self.pddl_parser.actions[action_name]
        param_keys = list(action['parameters'].keys())
        
        if len(bound_params) != len(param_keys):
            raise ValueError(f"动作 '{action_name}' 需要 {len(param_keys)} 个参数, 但提供了 {len(bound_params)} 个。 params: {bound_params}")

        param_map = dict(zip(param_keys, bound_params))

        effects = copy.deepcopy(action.get('effect', []))
        if not effects:
             return # 没有效果，直接返回

        if effects and effects[0] == 'and':
            effects_to_apply = effects[1:]
        else:
            effects_to_apply = [effects]
        # effects_to_apply = self.parse_effect(effects)

        for effect in effects_to_apply:
            # is_negated = isinstance(effect, list) and effect and effect[0] == 'not'
            # predicate_exp = effect[1] if is_negated else effect
            
            # if not isinstance(predicate_exp, list) or not predicate_exp: continue

            # pred_name = predicate_exp[0]
            # pred_params = [param_map.get(p, p) for p in predicate_exp[1:]]
            # process to formated predicate(with param) and the passed to next
            predicate_with_params = SceneGraphManager.fill_predicate_with_params(effect, param_map)
            self.apply_predicates(predicate_with_params)
            
        # 修改后，重建对象映射并重新提取所有谓词到物体节点中
        self._build_object_map()
        self.extract_all_predicates()
        
    def apply_predicates(self, predicate_with_param: List[Any]):
        """
        直接将一个具体化的谓词列表（包括肯定和否定形式）应用到场景图上。

        Args:
            predicates List[Any]: 一个谓词, 谓词本身是一个列表。
            例如:
            - Positive: ['item_on_surface', 'apple_1', 'table_1']
            - Negative: ['not', ['holding', 'agent_0', 'sponge_1']]
        """
        if not isinstance(predicate_with_param, list) or not predicate_with_param:
            return 
        
        predicate_exp_list = self.parse_predicate(predicate_with_param)

        for predicate_exp in predicate_exp_list:
            # 解析肯定/否定形式
            is_negated = (predicate_exp[0] == 'not')
            atomic_predicate = predicate_exp[1] if is_negated else predicate_exp

            if not isinstance(atomic_predicate, list) or not atomic_predicate:
                return 

            pred_name = atomic_predicate[0]
            pred_params = atomic_predicate[1:]

            # 使用核心的 _apply_effect 方法来修改场景图
            self._apply_effect(pred_name, pred_params, is_negated)

            # 在所有谓词都应用完毕后，刷新整个管理器的状态以确保一致性
            # self._build_object_map()
            # self.extract_all_predicates(
        

    def _apply_effect(self, pred_name: str, params: List[str], is_negated: bool):
        """[已修改] 内部辅助函数，用于具体执行单个效果的修改 (现在处理字典格式的link)。"""
        value_to_set = not is_negated
        
        # --- 新增对 next_to 的处理 ---
        if pred_name == "next_to":
            if len(params) != 3: return # 参数数量不符
            link_dict = {'relation': 'next_to', 'obj1': params[0], 'obj2': params[1], 'location': params[2]}
            if value_to_set:
                if link_dict not in self.scene_graph['links']:
                    self.scene_graph['links'].append(link_dict)
            else:
                if link_dict in self.scene_graph['links']:
                    self.scene_graph['links'].remove(link_dict)

        elif pred_name == 'item_on_surface':
            if len(params) != 2: return
            link_dict = {'relation': 'on', 'from': params[0], 'to': params[1]}
            if value_to_set:
                if link_dict not in self.scene_graph['links']: self.scene_graph['links'].append(link_dict)
            else:
                if link_dict in self.scene_graph['links']: self.scene_graph['links'].remove(link_dict)

        elif pred_name in ['item_in_receptacle', 'furniture_in_room', 'device_in_room']:
            if len(params) != 2: return
            link_dict = {'relation': 'in', 'from': params[0], 'to': params[1]}
            if value_to_set:
                if link_dict not in self.scene_graph['links']: self.scene_graph['links'].append(link_dict)
            else:
                if link_dict in self.scene_graph['links']: self.scene_graph['links'].remove(link_dict)
        
        elif pred_name == 'agent_at':
            agent_name, new_loc = params[0], params[1]
            if value_to_set:
                for agent in self.scene_graph['agent']:
                    if agent['name'] == agent_name: agent['location'] = new_loc; break
        
        elif pred_name == 'holding':
            agent_name, obj_name = params[0], params[1]
            for agent in self.scene_graph['agent']:
                if agent['name'] == agent_name: agent['holding'] = obj_name if value_to_set else None; break
        
        elif pred_name == 'handempty':
             agent_name = params[0]
             for agent in self.scene_graph['agent']:
                 if agent['name'] == agent_name:
                     if value_to_set: agent['holding'] = None; break
                     
        elif pred_name == "p_holding":
            person_name, obj_name = params[0], params[1]
            for person in self.scene_graph['person']:
                if person['name'] == person_name: person['p_holding'] = obj_name if value_to_set else None; break
        
        else: # 处理一元状态谓词
            if not params: return
            obj_name = params[0]
            if obj_name in self.object_map:
                obj_data = self.object_map[obj_name]['data']
                if 'states' not in obj_data: obj_data['states'] = {}
                obj_data['states'][pred_name] = value_to_set

    # ... get_all_predicates_from_sg 辅助函数保持不变 ...
    def get_all_predicates_from_sg(self) -> List[List[str]]:
        all_preds = []
        for obj_info in self.object_map.values():
            all_preds.extend(obj_info['data'].get('predicates', []))
        
        sorted_unique_preds = sorted([list(p) for p in set(tuple(map(tuple, p)) for p in all_preds)])
        return sorted_unique_preds
            
            
if __name__ == '__main__':
    # --- 输入数据 ---
    domain_file_path = 'work_space_lzh/policy_iteration/iter_data/pddl_data/domain_file/domain_0707.pddl'
    data_path = 'work_space_lzh/policy_iteration/iter/fix_plan/failed_save/failed_data_2025-07-11-17-11-03.json'
    
    with open(data_path, 'r') as file:
        data_list = json.load(file)
    sg = data_list[0]['searched_sg']
    
    domain_file_str = pathlib.Path(domain_file_path).read_text('utf-8')
    
    sg_manager = SceneGraphManager(sg, domain_file_str)

    # 1. 初始化管理器
    # sg_manager = SceneGraphManager(scene_graph_data, pddl_domain_string)
    
    # # 2. 从初始场景中提取所有谓词
    # print("--- 初始状态 ---")
    # initial_predicates = sg_manager.extract_all_predicates()
    # print("从Scene Graph提取的谓词:")
    # for p in sorted(initial_predicates):
    #     print(f"  {p}")
    # print("\n")
    
    # 3. 模拟执行一个动作: agent_0 拿起架子上的海绵
    # action: pick_from_surface ?ag - agent ?obj - physobj ?surface - physobj
    # 绑定参数: ?ag=agent_0, ?obj=sponge_1, ?surface=shelf_1
    print("--- 执行动作: pick_from_surface agent_0 sponge_1 shelf_1 ---")
    sg_manager.apply_action('pick_from_surface', ['agent_0', 'sponge_1', 'shelf_1'])

    # 4. 查看动作执行后的谓词和Scene Graph的变化
    print("\n--- 动作执行后的新状态 ---")
    updated_predicates = sg_manager.scene_graph['predicates']
    print("更新后的谓词:")
    for p in sorted(updated_predicates):
        print(f"  {p}")

    import json
    print("\n更新后的Scene Graph:")
    print(json.dumps(sg_manager.scene_graph, indent=4))
    
    # 5. 模拟执行第二个动作：agent_0 把海绵放到马桶上
    # action: place_on_surface ?ag - agent ?obj - physobj ?surface - furniture
    # 绑定参数: ?ag=agent_0, ?obj=sponge_1, ?surface=toilet_13
    print("\n--- 执行动作: place_on_surface agent_0 sponge_1 toilet_13 ---")
    sg_manager.apply_action('place_on_surface', ['agent_0', 'sponge_1', 'toilet_13'])
    
    # 6. 再次查看状态
    print("\n--- 第二个动作执行后的新状态 ---")
    final_predicates = sg_manager.scene_graph['predicates']
    print("最终谓词:")
    for p in sorted(final_predicates):
        print(f"  {p}")

    print("\n最终Scene Graph:")
    print(json.dumps(sg_manager.scene_graph, indent=4))