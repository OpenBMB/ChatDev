## FunctionDef get_config(company)
**get_config**: 此函数的功能是返回ChatChain的配置json文件路径。

**参数**:
- company: 指定的公司配置名称，位于CompanyConfig/目录下。

**代码描述**:
`get_config`函数用于获取ChatChain项目的配置文件路径。用户可以自定义部分配置文件，而其他文件将使用默认配置。该函数接受一个参数`company`，这是公司配置的名称，用于定位公司特定的配置文件目录。函数首先定义了配置文件所在的目录`config_dir`，该目录是基于传入的`company`参数动态确定的。同时，定义了默认配置文件的目录`default_config_dir`，用于在公司特定配置不存在时回退到默认配置。

函数接下来定义了一个列表`config_files`，包含了需要获取的配置文件名。对于这些配置文件，函数会尝试首先从公司特定的配置目录中查找，如果找不到，则从默认配置目录中获取。这一过程通过遍历`config_files`列表，对每个文件名构造完整的路径，并检查该路径是否存在来完成。如果公司特定的配置文件存在，则其路径被添加到`config_paths`列表中；否则，添加默认配置文件的路径。

最后，函数将`config_paths`列表中的路径转换为元组并返回。这样，调用者可以获得一个包含三个配置文件路径的元组，分别对应ChatChainConfig.json、PhaseConfig.json和RoleConfig.json文件。

**注意**:
- 确保`CompanyConfig/`目录下有`Default`子目录以及相应的默认配置文件，以防指定的公司配置不存在时能够正常回退到默认配置。
- 传入的`company`参数应确保在`CompanyConfig/`目录下有对应的子目录。

**输出示例**:
```python
('/path/to/CompanyConfig/YourCompany/ChatChainConfig.json', '/path/to/CompanyConfig/YourCompany/PhaseConfig.json', '/path/to/CompanyConfig/YourCompany/RoleConfig.json')
```
此示例展示了当指定公司配置存在时，函数返回的配置文件路径元组。路径将根据实际的文件系统和传入的`company`参数动态变化。
